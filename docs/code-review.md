# Code review

Reviewed scope: the FastAPI backend, Django frontend, templates, static assets, learning scripts and repository setup.

## Fixes

| Finding                                                                       | Change                                                                                                                                        |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Django's signing key was embedded in settings.                                | Read independent Django and JWT keys from the environment or an ignored `.env`; provide a setup script that preserves existing configuration. |
| API database selection depended on the working directory.                     | Resolve the default database from the backend directory and support an explicit SQLite URL.                                                   |
| Board deletion did not handle a network failure.                              | Catch HTTPX transport errors and show feedback rather than returning an unhandled exception.                                                  |
| Some task and board mutations contacted the API without checking the session. | Protect all workspace views with a shared session decorator; preserve ownership checks in the API.                                            |
| A failed task edit discarded the submitted title.                             | Redisplay the bound form and its error while retaining the text.                                                                              |
| Registration used the login form and missed the API's password minimum.       | Add a registration form with the same existing minimum.                                                                                       |
| API fields accepted whitespace-only content.                                  | Trim names and titles before length validation, including PATCH requests.                                                                     |
| Table setup and learning scripts wrote data during import.                    | Move execution behind documented entry points; repair the SQLite INSERT placeholder and target newly created sample rows.                     |
| Generated Python cache and local database files were tracked.                 | Add ignore rules. Previously tracked generated artifacts still require removal from the Git index before publication.                         |
| Python formatting and documentation were inconsistent.                        | Add production docstrings, useful type annotations, Ruff rules, template formatting, static-file formatting and continuous integration.       |
| A clean checkout lacked setup instructions and dependency manifests.          | Add pinned direct dependencies, `.env.example`, a safe setup script and README commands.                                                      |

## Verification

Automated checks cover account registration and login, JWT validation, account isolation, nested resource authorization, CRUD and PATCH semantics. Django regression tests cover session guards, POST-only actions, CSRF, API outages, retained form data and escaped user content. The setup utility has a test confirming that it does not replace existing secrets.

The interface is also checked in a real browser against isolated development databases, including account registration, login, task and board operations, filters, dialogs and responsive layouts. Dependency audit results reflect the advisory database at the time of the local audit; they do not establish that a project has no security risks.

## Remaining work before public hosting

Strengthen the account password policy, add login rate limiting and plan password recovery. Introduce versioned API database migrations. Deployment still needs an HTTPS and static-file configuration, production servers and an environment-specific review. These are separate from publishing the source as a portfolio project.

Git ignore rules affect the current tree, not earlier commits. Previously committed databases remain in Git history. Review that history before publication if it could contain personal or sensitive data; no history rewrite was performed as part of this review.

Current index cleanup remains necessary for the original `.pyc` and `.db` entries. Remove these entries from version control while preserving local databases before publishing the source.
