
# Licensing and dependency inventory

This project's MIT notice remains in `LICENSE`. Bootstrap downloads public wheels to ignored local storage. The repository does not vendor these packages or runtime images.

| Component | Pin | License / notice evidence |
| --- | --- | --- |
| attrs | 25.4.0 | Wheel metadata MIT; `licenses/LICENSE` |
| jsonschema | 4.25.1 | Wheel metadata MIT; `licenses/COPYING` |
| jsonschema-specifications | 2025.9.1 | Wheel metadata MIT; `licenses/COPYING` |
| referencing | 0.36.2 | Wheel metadata MIT; `licenses/COPYING` |
| rpds-py | 0.30.0 | Linux x86_64 CPython 3.14 wheel metadata MIT; `licenses/LICENSE` |
| pip (bootstrap / offline installer) | 25.2 | Wheel metadata MIT; retain bundled notices in `licenses/`, including notices for vendored components under their own licenses |
| actions/checkout | `11bd71901bbe5b1630ceea73d27597364c9af683` | MIT license at the pinned source |
| Docker Official Python image | Python 3.14.4 slim Bookworm, Linux amd64 digest in the workflow | CPython uses the PSF License Agreement and historical notices; the Debian base and included components retain their own package licenses |

The two lockfiles pin exact wheel hashes for the supported platform. Keep copyright and permission notices if redistributing MIT components, preserve the Python notices and account for Debian packages and bundled/transitive components before redistributing an image or wheelhouse. A package's top-level MIT declaration does not describe every vendored component. No redistribution is included in Phase 1B. OCI digest identity and published image metadata were checked; the image contents and complete OS license inventory require a separate inspection before redistribution. This inventory is not a vulnerability audit or an independent acceptance review.
