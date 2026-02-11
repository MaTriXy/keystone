import subprocess
from pathlib import Path

import modal

app = modal.App("bootstrap-devcontainer-docker-registry-cache")

# Persistent storage for cached layers
registry_volume = modal.Volume.from_name(
    "bootstrap-devcontainer-docker-registry-cache-volume",
    create_if_missing=True,
)

# Base image: Start with Python image, then add registry binary
registry_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ca-certificates", "wget")
    .run_commands(
        # Download and install Docker registry binary
        "wget -O /tmp/registry.tar.gz https://github.com/distribution/distribution/releases/download/v2.8.3/registry_2.8.3_linux_amd64.tar.gz",
        "tar -xzf /tmp/registry.tar.gz -C /usr/local/bin",
        "chmod +x /usr/local/bin/registry",
        "rm /tmp/registry.tar.gz",
    )
    .add_local_file("registry_config.yml", "/etc/docker/registry/config.yml")
)

auth_secret = modal.Secret.from_name("bootstrap-devcontainer-docker-registry-auth")


@app.function(
    image=registry_image,
    volumes={"/var/lib/registry": registry_volume},
    # CRITICAL SETTINGS
    secrets=[auth_secret],
    max_containers=1,  # enforce singleton writer
    min_containers=1,  # keep registry hot (faster builds)
    timeout=60 * 60 * 2,  # allow long pushes (2 hours)
    cpu=1,
    memory=1024,
)
@modal.concurrent(max_inputs=100)  # Allow concurrent requests
@modal.wsgi_app()
def registry():
    import os
    import socket
    import sys
    import time

    # Write htpasswd file from secret
    Path("/auth").mkdir(parents=True, exist_ok=True)
    Path("/auth/htpasswd").write_text(os.environ["HT_PASSWD"], encoding="utf-8")

    # Start the registry process as a background daemon
    print("Starting Docker registry process...", file=sys.stderr)
    proc = subprocess.Popen(
        ["registry", "serve", "/etc/docker/registry/config.yml"],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    print(f"Registry process started with PID: {proc.pid}", file=sys.stderr)

    # Wait for the registry to start listening on port 5000
    print("Waiting for registry to start listening...", file=sys.stderr)
    max_wait = 30
    for i in range(max_wait):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 5000))
            sock.close()
            if result == 0:
                print(f"Registry is listening on port 5000 after {i} seconds", file=sys.stderr)
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        # Timeout - check if process is still running
        if proc.poll() is not None:
            raise RuntimeError("Registry process died during startup")
        raise RuntimeError("Registry did not start listening on port 5000 within 30 seconds")

    # Simple WSGI proxy to forward requests to the registry
    def proxy_app(environ, start_response):
        import urllib.error
        import urllib.request

        # Build the URL to the local registry
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")
        url = f"http://localhost:5000{path}"
        if query:
            url += f"?{query}"

        # Read request body - handle both Content-Length and chunked transfer encoding.
        # Docker pushes use chunked encoding (no Content-Length), so we must read
        # wsgi.input fully in that case.
        content_length_str = environ.get("CONTENT_LENGTH", "")
        wsgi_input = environ["wsgi.input"]
        if content_length_str:
            try:
                content_length = int(content_length_str)
            except ValueError:
                content_length = 0
            request_body = wsgi_input.read(content_length) if content_length > 0 else None
        else:
            # No Content-Length: likely chunked transfer encoding.
            # Read all available data from wsgi.input.
            request_body = wsgi_input.read()
            if not request_body:
                request_body = None

        # Build headers from environ
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-")
                headers[header_name] = value
        if "CONTENT_TYPE" in environ:
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        # Set Content-Length for the upstream request when we have body data
        if request_body is not None:
            headers["Content-Length"] = str(len(request_body))
        # Remove Transfer-Encoding since we're sending the full body at once
        headers.pop("TRANSFER-ENCODING", None)
        headers.pop("Transfer-Encoding", None)

        # Forward the request
        method = environ.get("REQUEST_METHOD", "GET")
        req = urllib.request.Request(url, data=request_body, headers=headers, method=method)

        # The external hostname for rewriting Location headers
        external_host = environ.get("HTTP_HOST", "")

        def _rewrite_headers(raw_headers):
            """Rewrite Location headers from http://localhost:5000 to the external HTTPS URL."""
            result = []
            for k, v in raw_headers:
                if k.lower() == "location" and external_host:
                    v = v.replace("http://localhost:5000", f"https://{external_host}")
                    v = v.replace(f"http://{external_host}", f"https://{external_host}")
                result.append((k, v))
            return result

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                response_body = response.read()
                response_headers = _rewrite_headers([(k, v) for k, v in response.headers.items()])
                status = response.status
                start_response(f"{status} OK", response_headers)
                return [response_body]
        except urllib.error.HTTPError as e:
            response_body = e.read()
            response_headers = _rewrite_headers([(k, v) for k, v in e.headers.items()])
            start_response(f"{e.code} {e.reason}", response_headers)
            return [response_body]
        except Exception as e:
            start_response("502 Bad Gateway", [("Content-Type", "text/plain")])
            return [f"Error proxying to registry: {e}".encode()]

    return proxy_app
