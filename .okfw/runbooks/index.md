# runbooks

<!-- okfw:generated — maintained by okfw; edits here are overwritten -->

## Concepts

* [Bootstrap the macOS Host](bootstrap-the-macos-host--01a1664337ef.md) - Step-by-step: prepare an Apple Silicon Mac for a tf-labs lab with lab-bootstrap.mk.
* [Provision and Verify the Gateway](provision-and-verify-the-gateway--01a170011e5c.md) - Step-by-step: install the zero-trust gateway with lab-gateway.mk after the host checks pass, load the real credentials, run lab-gateway-verify.mk, and manage the allow list.
* [Provision the Python Stack](provision-the-python-stack--01a166e751e9.md) - Step-by-step: export the ZScaler chain, bring up the lab VM, and apply the python-stack playbook with its dry run and an idempotency re-run.
* [Run the Lab Behind a TLS-Inspecting Proxy](run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md) - Step-by-step: make the host, the gateway (Envoy) and every lab VM trust a TLS-inspecting proxy's CA chain (Zscaler as the example) through TLS_INSPECTION_DIR, verify it, rotate or remove it, and what is not covered.
* [Run the UAT Suites](run-the-uat-suites--01a17f21b82c.md) - How to run the lab's manual, story-form acceptance tests in labs/<lab>/uat/: the suites, the personas, the relation to the pytest suites and how to record a run.
* [Verify the Host and the Lab](verify-the-host-and-the-lab--01a16926b47d.md) - Step-by-step: verify the host after lab-bootstrap.mk, the gateway after lab-gateway.mk and the lab VMs after lab-provision.mk with the read-only pytest suites.

