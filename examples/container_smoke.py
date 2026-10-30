"""Build and verify the real container offline at runtime, including restart.

Docker builds may download pinned Python dependencies/base images. Test containers
have no network and no host port mappings; only synthetic data and fabricated tokens.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
import json, os, urllib.request, urllib.error
headers = {"Authorization": "Bearer fabricated-container-token", "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
def rpc(method, params, path="/mcp", supplied=None):
    request=urllib.request.Request("http://127.0.0.1:8769"+path,
      data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
      headers=headers if supplied is None else supplied)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        return error.code,None
assert os.getuid()==10001
assert rpc("tools/list",{},supplied={})[0]==401
status, discovered=rpc("tools/list",{})
assert status==200 and len(discovered["result"]["tools"])==45
assert rpc("tools/list",{},path="/app/mcp",supplied={"Origin":"https://external.invalid","X-MMM-Dashboard":"1","Content-Type":"application/json"})[0]==403
local_headers={"Origin":"http://127.0.0.1:8769","X-MMM-Dashboard":"1","Content-Type":"application/json","Accept":"application/json, text/event-stream"}
assert rpc("tools/list",{},path="/app/mcp",supplied=local_headers)[0]==200
if os.getenv("MMM_SMOKE_CREATE")=="1":
    status,result=rpc("tools/call",{"name":"generate_demo_dataset","arguments":{"request":{"dataset_id":"container-demo"}}})
    assert result["result"]["structuredContent"]["ok"]
status,result=rpc("tools/call",{"name":"validate_dataset","arguments":{"request":{"dataset_id":"container-demo"}}})
assert result["result"]["structuredContent"]["data"]["valid"]
status,result=rpc("resources/read",{"uri":"mmm://datasets/container-demo"},path="/app/mcp",supplied=local_headers)
assert "error" in result
print(json.dumps({"uid":os.getuid(),"tools":45,"unauthenticated_mcp":401,"cross_origin_dashboard":403,"local_dashboard":200,"tenant_isolation":True,"dataset_valid":True}))
"""


def run(*args, capture=False, check=True, timeout=900):
    return subprocess.run(
        ["docker", *map(str, args)],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=check,
        timeout=timeout,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suffix = uuid4().hex
    image, volume, container = "mmm-smoke:" + suffix, "mmm-data-" + suffix, "mmm-smoke-" + suffix
    receipt = {"synthetic": True, "runtime_network": "none", "published_ports": False}
    with tempfile.TemporaryDirectory(prefix="mmm-container-") as task:
        users = Path(task) / "users.json"
        users.write_text(
            json.dumps(
                {
                    "analyst": {
                        "role": "analyst",
                        "token_sha256": hashlib.sha256(b"fabricated-container-token").hexdigest(),
                    }
                }
            )
        )
        users.chmod(0o644)
        try:
            run("build", "--tag", image, "--file", "deploy/Dockerfile", ".")
            receipt["base_image"] = (ROOT / "deploy/Dockerfile").read_text().splitlines()[0]
            receipt["image_id"] = run(
                "image", "inspect", "--format", "{{.Id}}", image, capture=True
            ).stdout.strip()
            run("volume", "create", volume, capture=True)
            for attempt in range(2):
                run(
                    "run",
                    "--detach",
                    "--name",
                    container,
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--pids-limit",
                    "256",
                    "--memory",
                    "1g",
                    "--cpus",
                    "2",
                    "--tmpfs",
                    "/tmp:size=256m,mode=1777",
                    "--mount",
                    f"type=volume,source={volume},target=/artifacts",
                    "--mount",
                    f"type=bind,source={users},target=/run/secrets/mmm_users,readonly",
                    image,
                    capture=True,
                )
                for _ in range(45):
                    probe = run(
                        "exec",
                        "--env",
                        f"MMM_SMOKE_CREATE={int(attempt == 0)}",
                        container,
                        "python",
                        "-c",
                        PROBE,
                        capture=True,
                        check=False,
                        timeout=45,
                    )
                    if probe.returncode == 0:
                        receipt["initial" if attempt == 0 else "restart"] = json.loads(probe.stdout)
                        break
                    # Only retry startup refusal, not failed assertions or partial test runs.
                    if "Connection refused" not in probe.stderr:
                        raise RuntimeError(probe.stderr[-3000:])
                    time.sleep(1)
                else:
                    raise RuntimeError("Container failed to become ready")
                run("rm", "--force", container, capture=True)
            receipt["restart_persistence"] = True
        finally:
            run("rm", "--force", container, capture=True, check=False)
            run("volume", "rm", volume, capture=True, check=False)
            run("image", "rm", image, capture=True, check=False)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
