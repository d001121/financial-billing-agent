import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dashboardAnalytics } from '../src/utils/dashboardAnalytics.ts';
const now = new Date(2026, 9, 24, 12);
const task = (id, at, status = 'completed', extra = {}) => ({ id, title: id, revision: 1, created_at: at, status, ...extra });

test('creation cohorts sum to the same status, entity and heatmap totals', () => {
  const input = [task('a',new Date(2026,9,18,7),'completed',{accounting_entity:'A'}),task('b',new Date(2026,9,24,11),'waiting_input',{accounting_entity:'A'}),task('c',new Date(2026,9,24,12),'failed',{accounting_entity:'B'}),task('d',new Date(2026,9,23,8),'processing')];
  const result = dashboardAnalytics(input,7,now);
  assert.equal(result.tasks.length,4);
  assert.deepEqual(result.counts,{completed:1,review:1,active:1,attention:1});
  assert.equal(result.daily.reduce((sum,d)=>sum+d.total,0),4);
  assert.equal(result.heat.reduce((sum,c)=>sum+c[2],0),4);
  assert.equal(result.entities.reduce((sum,c)=>sum+c[1],0),4);
  assert.equal(result.start,'2026-10-18');
  assert.equal(result.end,'2026-10-24');
  assert.equal(result.heat.find(c=>c[0]===7 && c[1]===6)[2],1);
});
test('date filtering uses creation time, not later updates, and excludes invalid/future dates',()=>{
  const input=[task('old',new Date(2026,9,17,23,59),'completed',{updated_at:now.toISOString()}),task('edge',new Date(2026,9,18,0)),task('late',new Date(2026,9,25,0)),task('invalid','bad')];
  const result=dashboardAnalytics(input,7,now);
  assert.deepEqual(result.tasks.map(t=>t.id),['edge']);
  assert.equal(result.undated,1);
});
test('current revision approval is classified with the existing business presentation contract',()=>{
  const result=dashboardAnalytics([task('approved',now,'processing',{approval:{decision:'approve',binding:{revision:1}}}),task('old-approval',now,'processing',{approval:{decision:'approve',binding:{revision:0}}})],7,now);
  assert.equal(result.counts.completed,1); assert.equal(result.counts.active,1);
});
test('empty data preserves seven actual dates and zero quantities, without example values',()=>{
  const result=dashboardAnalytics([],7,now);
  assert.equal(result.daily.length,7);
  assert.equal(result.tasks.length,0);
  assert.equal(result.heat.length,168);
  assert.ok(result.daily.every(d=>d.total===0));
  assert.deepEqual(result.entities,[]);
});
test('all time and a window crossing a year retain calendar boundaries',()=>{
  const input=[task('dec',new Date(2025,11,31,16)),task('jan',new Date(2026,0,1,3))];
  const result=dashboardAnalytics(input,7,new Date(2026,0,2));
  assert.equal(result.start,'2025-12-27'); assert.equal(result.tasks.length,2);
  const all=dashboardAnalytics(input,null,new Date(2026,0,2));
  assert.equal(all.start,'2025-12-31'); assert.equal(all.daily.length,3);
});
test('custom dates include the entire end day and filter all chart projections together',()=>{
  const result=dashboardAnalytics([
    task('before',new Date(2026,9,20,23,59)),task('start',new Date(2026,9,21,0)),
    task('end',new Date(2026,9,23,23,59,59,999)),task('after',new Date(2026,9,24,0)),
  ],{start:'2026-10-21',end:'2026-10-23'},now);
  assert.deepEqual(result.tasks.map(t=>t.id),['start','end']);
  assert.equal(result.daily.length,3); assert.equal(result.end,'2026-10-23');
  assert.equal(result.counts.completed,2);
  assert.equal(result.heat.reduce((sum,c)=>sum+c[2],0),2);
});
test('custom dates allow one day and reject reversed or impossible calendar dates',()=>{
  assert.equal(dashboardAnalytics([], {start:'2026-10-24',end:'2026-10-24'}, now).daily.length,1);
  for(const bounds of [{start:'2026-10-25',end:'2026-10-24'},{start:'2026-02-30',end:'2026-10-24'}]) {
    assert.throws(()=>dashboardAnalytics([],bounds,now),RangeError);
  }
});
