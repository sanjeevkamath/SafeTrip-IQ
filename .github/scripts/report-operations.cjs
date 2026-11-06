// One issue per problem category. No messages on an unchanged unhealthy state.
module.exports = async ({github, context, core, kind, failed}) => {
  const title = kind === 'freshness'
    ? '[Operations] Production data is stale or unavailable'
    : '[Operations] Advisory refresh failed — inspect committed stages'
  const {owner, repo} = context.repo
  const marker = `<!-- safetrip-operations:${kind} -->`
  const issues = await github.paginate(github.rest.issues.listForRepo, {owner, repo, state:'open', per_page:100})
  const existing = issues.find(issue => !issue.pull_request && issue.title === title
    && issue.user?.login === 'github-actions[bot]' && issue.body?.includes(marker))
  if (failed && !existing) {
    const run = `${context.serverUrl}/${owner}/${repo}/actions/runs/${context.runId}`
    await github.rest.issues.create({owner, repo, title, body:
      `${marker}\nInvestigation required: ${run}\n\nPublic health: https://safetripiq.vercel.app/api/health\n\n` +
      'Check workflow artifacts and the database run ledger before retrying. A failed run can follow a committed import or publication. ' +
      'Recovery instructions: docs/operations.md. No credentials belong in this issue.'})
    core.info('Opened one operations issue. Configure repository/Actions notifications for email delivery.')
  } else if (!failed && existing && kind === 'freshness') {
    await github.rest.issues.createComment({owner, repo, issue_number:existing.number,
      body:'The daily public health check now passes for both source retrieval and score publication. Closing the freshness alert.'})
    await github.rest.issues.update({owner, repo, issue_number:existing.number, state:'closed'})
  }
}
