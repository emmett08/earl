# Pre-launch review amendment: 0.1.2 to 0.1.3

Revision 0.1.2 was frozen locally as `freeze-preflight-review-0.1.2.json`
but was **not launched**. Independent review found two preflight mismatches
before any new model call.

First, the proposed direct DNS/TLS socket probe ignored proxy variables
forwarded to the live Codex process. It could reject a viable proxied runner
or pass a route different from the actual agent route. Revision 0.1.3 passes
the same `HTTPS_PROXY`, `HTTP_PROXY` and `NO_PROXY` environment to the
credential-free probe and uses an unauthenticated HTTPS request to
`https://api.openai.com/v1/models`. An HTTP 401 response demonstrates that
the effective route reached the provider over TLS; a DNS, proxy, TLS or
other HTTP failure blocks live acquisition. This request sends no provider
key and requests no model inference. A symlinked resolver target remains
mounted as one read-only file, never all of `/run`.

Second, the previous writable mount probe used a fixed `.runner-probe` name
inside the copied trial. A candidate could have produced that file in an
earlier stage, in which case preflight would overwrite and unlink it after
the packet/source digest had been bound. Revision 0.1.3 generates a fresh
unpredictable name and opens it exclusively. A collision fails explicitly;
only the file created by the probe is removed. The read-only probe likewise
uses a fresh exclusive name and accepts only a permission/read-only error.

No source fixture, assessor, argument packet, treatment, allocation, model,
case oracle, analysis endpoint, time cap or price rule changes. The 0.1.1
DNS-blocked run remains retained as infrastructure evidence, not part of a
new treatment effect. This amendment and its 0.1.3 freeze precede CI
validation and all new assigned sessions.
