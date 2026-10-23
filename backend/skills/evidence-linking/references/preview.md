# Source preview

The host supplies immutable `source` blocks, current `revision`, and an optional display `target` with `anchor`, `quote`, `field`, and `value`. This function neither reparses nor changes the financial result.

Output includes `kind`, `blocks`, `target`, `preview_version`, and `representation`. `original_structure` means an Excel sheet/row/cell or Word paragraph/table view built from the original parser. It is not a pixel-identical Office rendering. The host attaches the original file URL and download entry.

`target.located` locates a unique saved block; `location_level=cell` additionally requires a unique matching cell. Amount matching uses decimal tokens, so 50 cannot select 150. Multiple identical values retain a row location. PDF/image boxes are returned only when the source supplied a box and an explicit normalized/pixel unit and dimensions; unknown OCR coordinates are never guessed. A quote found in structured OCR does not prove the same text is searchable in the rendered PDF. The viewer must report that distinction.

Implementation basis: LangChain Docs MCP document loader index and Deep Agents skills; API MCP `SkillsMiddleware` provides discovery and native tool binding, not this domain source/cell target projection. This minimal business function stays in the portable evidence Skill; HTTP delivery stays in the host.
