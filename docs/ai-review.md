# AI planning review

The AI feature has two explicit steps: preview proposals, then save reviewed tasks. The planner UI gives these actions separate forms and keeps the existing Django templates, CSS and plain JavaScript stack.

## Changes

| Area                   | Result                                                                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AI entry point         | A distinct dark green module with a mint action opens the planner from the board.                                                                       |
| Goal and range         | Labeled inputs, example goals, a character counter and matching client/server limits.                                                                   |
| Generation             | A waiting state blocks repeated submissions. Typed input survives model errors and timeouts.                                                            |
| Review                 | Editable titles, skip controls, a selected-task count and an explicit save action. Review also works without JavaScript.                                |
| Provider configuration | Unsupported providers, missing model names, invalid URLs and invalid timeouts return a controlled unavailable response.                                 |
| Provider response      | Invalid JSON envelopes and malformed task output produce safe errors rather than leaking upstream diagnostics.                                          |
| Proposal validation    | Enforce the requested count, title lengths and unique proposals; reject titles already on the selected board.                                           |
| Access                 | Authenticate and check board ownership before resolving the provider or generating proposals. Other boards' titles are excluded from the prompt.        |
| Demo mode              | Generate the requested number of sample tasks within the accepted range and visibly identify demo output. The provider label is assigned by the server. |
| Formset validation     | Limit the review to fifty forms, reject an empty selection and duplicate edited titles, and handle missing management fields without an exception.      |
| Saving                 | Use one batch request and one transaction. Preserve edits and selection after failures; warn about ambiguous network outcomes before retrying.          |
| Documentation          | Add docstrings and type annotations, update configuration examples and describe the preview/save boundary.                                              |

## Regression coverage

Backend tests cover authentication, account ownership, legacy and missing boards, request boundaries, output parsing, duplicate proposals, provider failures and atomic batch writes. Provider tests use deterministic fakes and mocked HTTP responses.

Django tests cover form limits, session expiry, CSRF, error messages, escaped text, retained user input and saving only the selected titles. A forged form count is capped before rendering, and missing formset management fields produce validation feedback.

The Playwright suite starts isolated API and Django servers with temporary databases and the demo provider. It exercises the complete review/save flow, the pending state, empty selection, responsive widths and use without JavaScript. These tests do not use or alter development databases. A separate local integration check exercised the configured Ollama model with a three-task request.

## Remaining limits

Generation is synchronous and can take tens of seconds on a local model. The model timeout is bounded and the browser displays a waiting state. No background queue, cancellation or inference rate limiting is implemented.

Batch persistence is transactional but does not provide an idempotency key. A lost response can leave the result of a save uncertain; the UI asks the user to inspect the board before retrying. Previously issued JWTs and the project's existing account policy retain the limitations documented in the README.

The prompt contains the user's goal and existing task titles. JSON separation helps preserve their structure; it does not establish immunity to prompt injection. Output validation and the separate, explicit save action remain the application boundaries.
