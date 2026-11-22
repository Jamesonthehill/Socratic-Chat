# HTTP semantics for a resource API
A safe method has essentially read-only intended semantics. GET is safe. Idempotency means multiple identical requests have the same intended server effect as one such request; it does not require identical response bodies or status codes. PUT and DELETE are idempotent but not safe. Logging an access does not by itself make GET unsafe.

PUT creates or replaces the state of the target resource at a client-known URI according to the representation supplied. POST asks the target resource to process the representation according to its own semantics, such as creating a child whose URI the server chooses. POST is not inherently idempotent; an API can add an explicit deduplication contract.

201 Created indicates that one or more resources were created. A Location header can identify the created resource. 404 indicates that the origin server did not find a current representation for the target resource or is unwilling to disclose that one exists. A successful DELETE need not return the same status on a second call for the operation to remain idempotent.
