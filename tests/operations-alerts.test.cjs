const test = require('node:test')
const assert = require('node:assert/strict')
const report = require('../.github/scripts/report-operations.cjs')

test('operations alerts notify on new failures and recovery, not unchanged failures', async () => {
  const calls=[]
  let issues=[]
  const github={rest:{issues:{listForRepo(){},
    async create(value){calls.push(['create',value])},
    async createComment(value){calls.push(['comment',value])},
    async update(value){calls.push(['update',value])}}},paginate:async()=>issues}
  const context={repo:{owner:'owner',repo:'repo'},serverUrl:'https://github.com',runId:123}
  const core={info(){}}
  await report({github,context,core,kind:'freshness',failed:true})
  assert.equal(calls.length,1)
  issues=[{title:calls[0][1].title,body:calls[0][1].body,user:{login:'github-actions[bot]'},number:1}]
  await report({github,context,core,kind:'freshness',failed:true})
  assert.equal(calls.length,1)
  await report({github,context,core,kind:'freshness',failed:false})
  assert.deepEqual(calls.map(c=>c[0]),['create','comment','update'])
  assert.equal(calls[2][1].state,'closed')
})
