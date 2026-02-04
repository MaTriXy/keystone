The verification timeout on the unit test is much too short. 

The verifier should build the image using network host rather than div container build. 

This error message looks wrong:
      "error_message": "2026-02-03T22:16:37.275-0800 8711679040 root bootstrap_devcontainer_cli.py:534 Starting bootstrap_devcontainer CLI, version: branch='HEAD' commit_count=2206 commit_timestamp='2025-12-17T08:38:12' git_hash='0a88cccd5188074de96f54a4b6b44a63971ac157' is_dirty=False\nWorking from git tree: \u001b[36m4906fc180038c07fb8a68171a89f6422f5cfb5e1\u001b[0m\nCache key - git tree: 4906fc180038c07fb8a68171a89f6422f5cfb5e1, prompt MD5: 124364e64e22aec6d789e7f1ffc5ea4b, config: {\"agent_cmd\":\"claude\",\"max_budget_usd\":10.0,\"agent..., version: (none)\n\u001b[35mCACHE MISS: Running agent (log: /Users/thad/.bootstrap_devcontainer/log.sqlite)\u001b[0m\nCreating Modal sandbox with Docker...\nModal sandbox created: sb-ooRQhUPXZcBEsXnxGcSVLW\n  Dashboard: https://modal.com/apps/bootstrap-devcontainer-sandbox\n  Shell:     modal shell sb-ooRQhUPXZcBEsXnxGcSVLW\n2026-02-03T22:16:40.807-0800 8711679040 bootstrap_devcontainer.modal modal_runner.py:134 [dockerd] Running: /start-dockerd.sh\n2026-02-03T22:16:42.371-0800 8711679040 bootstrap_devco",

Done:
* Remind the agent to set the right build context (workspace root) in the devcontainer.json.
