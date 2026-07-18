# Extra CA certificates for Docker builds

If your network re-signs TLS traffic (a TLS-inspecting proxy), package
downloads inside `docker build` fail certificate verification. Drop the
proxy's root CA here as a PEM file with a `.crt` extension (for example
`proxy-root.crt`) and rebuild — both Dockerfiles install every `.crt` in
this directory into the build container's trust store.

On normal networks, leave this directory as is; builds work unchanged.
Everything here except this README is gitignored — never commit real
certificates.
