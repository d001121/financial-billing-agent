"""Offline OBS/OCR contracts using synthetic fixtures and an injected Huawei SDK."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from langchain_community.document_loaders import PDFPlumberLoader  # load native extensions before patch.dict(sys.modules)


spec = importlib.util.spec_from_file_location(
    "document_intake_obs", Path(__file__).parents[1] / "scripts" / "skill.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OBSIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.events = []
        self.upload_status = 200
        self.client = Mock()
        self.client.putFile.side_effect = self.upload
        self.client.createSignedUrl.side_effect = self.sign
        self.sdk = types.ModuleType("obs")
        self.sdk.ObsClient = Mock(return_value=self.client)
        self.sdk.PutObjectHeader = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
        self.sdk_patch = patch.dict(sys.modules, {"obs": self.sdk})
        self.sdk_patch.start()
        self.options = {
            "enabled": True,
            "access_key_id": "test-access",
            "secret_access_key": "test-secret",
            "server": "https://obs.example.test",
            "bucket": "synthetic-bucket",
            "object_prefix": "synthetic",
            "socket_timeout": 60,
        }
        self.ocr = Mock(side_effect=self.recognize)

    def tearDown(self):
        self.sdk_patch.stop()
        self.temp.cleanup()

    def upload(self, bucket, key, path, **kwargs):
        self.events.append(("upload", key, Path(path).read_bytes()))
        return SimpleNamespace(
            status=self.upload_status,
            body=SimpleNamespace(etag="synthetic-etag"),
            requestId="synthetic-request",
            errorCode="SyntheticFailure" if self.upload_status >= 300 else None,
        )

    def sign(self, method, *, bucketName, objectKey, expires):
        self.events.append(("sign", objectKey))
        return {"signedUrl": f"https://files.example/{objectKey}?signature=synthetic"}

    def recognize(self, **kwargs):
        self.events.append(("ocr", kwargs["payload"]["file"]))
        return "Synthetic handling charge USD 10"

    def image(self, name="synthetic.png", color="white"):
        path = self.root / name
        Image.new("RGB", (30, 20), color).save(path)
        return path

    def intake(self, path, **kwargs):
        options = {"obs_options": self.options, "ocr_request": self.ocr}
        options.update(kwargs)
        return module.intake_document(path, output_dir=self.root / "artifacts", **options)

    def receipts(self, result):
        return result["sources"][0]["metadata"].get("obs_objects", [])

    def test_missing_url_uploads_then_ocr_uses_signed_url(self):
        path = self.image()
        result = self.intake(path)
        self.assertEqual(result["status"], "ready")
        self.assertEqual([event[0] for event in self.events], ["upload", "sign", "ocr"])
        bucket, key, upload_path = self.client.putFile.call_args.args
        self.assertEqual(bucket, self.options["bucket"])
        self.assertEqual(Path(upload_path), path)
        self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), key)
        self.client.createSignedUrl.assert_called_once_with(
            "GET", bucketName=bucket, objectKey=key, expires=3600
        )
        self.assertEqual(
            self.ocr.call_args.kwargs["payload"],
            {"file": f"https://files.example/{key}?signature=synthetic", "task": "orderChange", "callBack": "", "taskType": ""},
        )
        receipt = self.receipts(result)[0]
        self.assertEqual(receipt["object_key"], key)
        self.assertEqual(receipt["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(receipt["status"], 200)
        self.assertEqual(receipt["etag"], "synthetic-etag")
        self.assertNotIn("signature=", json.dumps(receipt))
        self.assertNotIn("signedUrl", receipt)
        self.client.close.assert_called_once()

    def test_disabled_obs_does_not_create_client(self):
        result = self.intake(self.image(), obs_options={**self.options, "enabled": False})
        self.assertEqual(result["status"], "waiting_url")
        self.sdk.ObsClient.assert_not_called()
        self.client.putFile.assert_not_called()
        self.ocr.assert_not_called()
        self.assertEqual(self.receipts(result), [])

    def test_explicit_source_url_has_priority_over_resolver_and_obs(self):
        resolver = Mock(return_value="https://files.example/resolved.png")
        result = self.intake(self.image(), source_url="https://files.example/caller.png", url_resolver=resolver)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.ocr.call_args.kwargs["payload"]["file"], "https://files.example/caller.png")
        resolver.assert_not_called()
        self.sdk.ObsClient.assert_not_called()

    def test_resolver_url_has_priority_over_obs(self):
        resolver = Mock(return_value="https://files.example/resolved.png")
        result = self.intake(self.image(), url_resolver=resolver)
        self.assertEqual(result["status"], "ready")
        resolver.assert_called_once()
        self.assertEqual(self.ocr.call_args.kwargs["payload"]["file"], "https://files.example/resolved.png")
        self.sdk.ObsClient.assert_not_called()

    def test_upload_http_failure_is_visible_and_blocks_ocr(self):
        self.upload_status = 503
        result = self.intake(self.image())
        self.assertTrue(any(issue["code"] == "obs_upload_failed" for issue in result["issues"]))
        self.assertNotEqual(result["status"], "ready")
        self.client.createSignedUrl.assert_not_called()
        self.ocr.assert_not_called()
        self.assertEqual(self.receipts(result), [])
        self.client.close.assert_called_once()

    def test_guard_rejection_before_upload_sends_no_requests(self):
        guard = Mock(side_effect=RuntimeError("synthetic pause before upload"))
        result = self.intake(self.image(), request_guard=guard)
        guard.assert_called_once()
        self.client.putFile.assert_not_called()
        self.client.createSignedUrl.assert_not_called()
        self.ocr.assert_not_called()
        self.assertNotEqual(result["status"], "ready")
        self.client.close.assert_called_once()

    def test_guard_rejection_before_ocr_keeps_upload_receipt(self):
        guard = Mock(side_effect=[None, RuntimeError("synthetic pause before OCR")])
        result = self.intake(self.image(), request_guard=guard)
        self.assertEqual(guard.call_count, 2)
        self.client.putFile.assert_called_once()
        self.ocr.assert_not_called()
        self.assertNotEqual(result["status"], "ready")
        self.assertEqual(len(self.receipts(result)), 1)
        self.assertEqual(self.receipts(result)[0]["status"], 200)
        self.client.close.assert_called_once()

    def test_each_pdf_slice_upload_preserves_original_page_mapping(self):
        path = self.root / "synthetic-long.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=300)
        with path.open("wb") as stream:
            writer.write(stream)
        result = self.intake(path, pdf_pages_per_slice=2)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.client.putFile.call_count, 3)
        self.assertEqual(self.ocr.call_count, 3)
        self.assertEqual([receipt["original_pages"] for receipt in self.receipts(result)], [[1, 2], [3, 4], [5]])
        self.assertEqual(
            [len(PdfReader(call.args[2]).pages) for call in self.client.putFile.call_args_list],
            [2, 2, 1],
        )
        self.assertTrue(all(receipt["source_id"] == result["sources"][0]["source_id"] for receipt in self.receipts(result)))
        self.client.close.assert_called_once()

    def test_each_tiff_frame_upload_preserves_original_frame_mapping(self):
        path = self.root / "synthetic-frames.tiff"
        Image.new("RGB", (30, 20), "white").save(
            path, save_all=True, append_images=[Image.new("RGB", (20, 30), "black")]
        )
        result = self.intake(path)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.client.putFile.call_count, 2)
        self.assertEqual(self.ocr.call_count, 2)
        self.assertEqual([receipt["frame"] for receipt in self.receipts(result)], [1, 2])
        self.assertEqual([block["frame"] for block in result["sources"][0]["blocks"]], [1, 2])
        self.assertTrue(all(Path(call.args[2]).suffix == ".png" for call in self.client.putFile.call_args_list))
        self.client.close.assert_called_once()

    def test_object_key_is_stable_for_same_content_and_changes_with_content(self):
        first = self.image("first.png")
        same = self.root / "same.png"
        same.write_bytes(first.read_bytes())
        different = self.image("different.png", color="black")
        for path in (first, same, different):
            self.assertEqual(self.intake(path)["status"], "ready")
        keys = [call.args[1] for call in self.client.putFile.call_args_list]
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], keys[2])
        self.assertTrue(all(key.startswith("synthetic/workorder-agent/") and key.endswith(".png") for key in keys))
        self.assertEqual(self.client.close.call_count, 3)

    def test_upload_transport_exception_closes_client_and_blocks_ocr(self):
        self.client.putFile.side_effect = OSError("synthetic connection reset")
        result = self.intake(self.image())
        self.assertTrue(any(issue["code"] == "obs_upload_failed" for issue in result["issues"]))
        self.client.createSignedUrl.assert_not_called()
        self.ocr.assert_not_called()
        self.client.close.assert_called_once()

    def test_signature_failure_blocks_ocr_and_keeps_completed_upload_receipt(self):
        for failure in (RuntimeError("synthetic signing failure"), {"signedUrl": "http://files.example/unsigned.png"}):
            with self.subTest(failure=type(failure).__name__):
                self.client.putFile.reset_mock()
                self.client.close.reset_mock()
                self.client.createSignedUrl.side_effect = failure if isinstance(failure, Exception) else None
                self.client.createSignedUrl.return_value = failure if isinstance(failure, dict) else None
                result = self.intake(self.image())
                self.client.putFile.assert_called_once()
                self.ocr.assert_not_called()
                self.assertNotEqual(result["status"], "ready")
                self.assertTrue(any(issue["code"] == "obs_upload_failed" for issue in result["issues"]))
                receipt = self.receipts(result)[0]
                self.assertEqual(receipt["status"], 200)
                self.assertEqual(receipt["request_id"], "synthetic-request")
                self.assertNotIn("signedUrl", receipt)
                self.client.close.assert_called_once()

    def test_order_change_keeps_exact_document_values_without_inventing_fields(self):
        documents = [
            {"invoiceNumber": "SYN-01", "page_index": 19, "currency": None,
             "chargeList": [{"chargeName": "码头费", "amount": "1,200.00", "quantity": "2"}],
             "service_extension": {"confidence": "unknown"}},
            {"invoiceNumber": None, "chargeList": [{"chargeName": "Doc Fee", "amount": "0.00"}]},
        ]
        response = {"success": True, "data": {"list": documents}}
        result = self.intake(self.image(), ocr_response_format="orderChange", ocr_request=lambda **_: response)
        self.assertEqual(result["status"], "ready")
        blocks = result["sources"][0]["blocks"]
        self.assertEqual(len(blocks), 2)
        self.assertEqual([json.loads(block["text"]) for block in blocks], documents)
        self.assertEqual([block["response_pointer"] for block in blocks], ["/data/list/0", "/data/list/1"])
        self.assertTrue(all(block["kind"] == "ocr_structured" and block["authoritative"] for block in blocks))
        self.assertTrue(all("page" not in block for block in blocks))
        self.assertEqual(json.loads(Path(blocks[0]["raw_response"]).read_text(encoding="utf-8")), response)

    def test_order_change_uses_pdf_transfer_mapping_instead_of_service_page_index(self):
        path = self.root / "synthetic-structured.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=200, height=300)
        with path.open("wb") as stream:
            writer.write(stream)
        response = {"success": True, "data": {"list": [{"invoiceNumber": "SYN-PDF", "page_index": 50}]}}
        result = self.intake(path, pdf_pages_per_slice=2, ocr_response_format="orderChange",
                             ocr_request=lambda **_: response)
        blocks = [block for block in result["sources"][0]["blocks"] if block["kind"] == "ocr_structured"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual([block["original_pages"] for block in blocks], [[1, 2], [3]])
        self.assertNotIn("page", blocks[0])
        self.assertEqual(blocks[1]["page"], 3)
        self.assertTrue(all(json.loads(block["text"])["page_index"] == 50 for block in blocks))

    def test_order_change_failed_or_empty_response_cannot_produce_ready_blocks(self):
        for response, code in (
            ({"success": False, "data": {"list": [{"invoiceNumber": "SYN-FAIL"}]}}, "ocr_service_failed"),
            ({"success": True, "data": {"list": []}}, "ocr_response_invalid"),
        ):
            with self.subTest(response=response):
                result = self.intake(self.image(), ocr_response_format="orderChange", ocr_request=lambda **_: response)
                self.assertNotEqual(result["status"], "ready")
                self.assertTrue(any(issue["code"] == code and issue["blocking"] for issue in result["issues"]))
                self.assertEqual(result["sources"][0]["blocks"], [])
                raw = next(item for item in result["artifacts"] if item["kind"] == "ocr_raw")
                self.assertEqual(json.loads(Path(raw["path"]).read_text(encoding="utf-8")), response)

    def test_explicit_text_pointer_takes_priority_over_structured_response_mode(self):
        response = {"success": True, "data": {"text": "Synthetic explicit text USD 10",
                    "list": [{"invoiceNumber": "SYN-STRUCTURED", "amount": "999"}]}}
        result = self.intake(self.image(), ocr_response_format="orderChange", ocr_text_pointer="/data/text",
                             ocr_request=lambda **_: response)
        self.assertEqual(result["status"], "ready")
        blocks = result["sources"][0]["blocks"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["kind"], "ocr_text")
        self.assertEqual(blocks[0]["text"], "Synthetic explicit text USD 10")
        self.assertNotIn("response_pointer", blocks[0])


if __name__ == "__main__":
    unittest.main()
