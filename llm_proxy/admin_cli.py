"""LLM Proxy Admin CLI - standalone management tool."""
import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

CONFIG_SEARCH_PATHS = [Path("config.json"), Path.home() / ".llm-admin" / "config.json"]


def _load_config(config_path):
    if config_path:
        p = Path(config_path)
        if p.exists():
            return json.loads(p.read_text())
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    for p in CONFIG_SEARCH_PATHS:
        if p.exists():
            return json.loads(p.read_text())
    return {}


def _request(method, path, data=None, base_url="", admin_key=""):
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {admin_key}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        error_body = e.read().decode()
        try:
            error = json.loads(error_body)
            print(f"Error: {error.get('detail', error_body)}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"Error: {error_body}", file=sys.stderr)
        sys.exit(1)


def cmd_model_add(args):
    result = _request("POST", "/admin/models", {"id": args.id, "provider": args.provider,
        "api_base": args.api_base, "api_key": args.api_key, "model_name": args.model_name, "rpm": args.rpm},
        args.base_url, args.admin_key)
    print(f"Added model: {result['id']}")


def cmd_model_list(args):
    result = _request("GET", "/admin/models", base_url=args.base_url, admin_key=args.admin_key)
    for b in result["data"]:
        print(f"  {b['id']:20s} {b['provider']:10s} {b['model_name']}")
    if not result["data"]:
        print("  (no models)")


def cmd_model_remove(args):
    _request("DELETE", f"/admin/models/{args.id}", base_url=args.base_url, admin_key=args.admin_key)
    print(f"Removed model: {args.id}")


def cmd_group_add(args):
    models = args.models.split(",")
    weights = [float(w) for w in args.weights.split(",")]
    result = _request("POST", "/admin/groups", {"name": args.name, "models": models, "weights": weights, "fallback": args.fallback},
        args.base_url, args.admin_key)
    print(f"Added group: {result['name']} with models {models}")


def cmd_group_list(args):
    result = _request("GET", "/admin/groups", base_url=args.base_url, admin_key=args.admin_key)
    for g in result["data"]:
        members = ", ".join(f"{m['model_id']}({m['weight']})" for m in g.get("members", []))
        fallback = f" -> {g['fallback']}" if g.get("fallback") else ""
        print(f"  {g['name']}: [{members}]{fallback}")
    if not result["data"]:
        print("  (no groups)")


def cmd_group_remove(args):
    _request("DELETE", f"/admin/groups/{args.name}", base_url=args.base_url, admin_key=args.admin_key)
    print(f"Removed group: {args.name}")


def cmd_group_set_fallback(args):
    _request("PUT", f"/admin/groups/{args.name}/fallback?fallback={args.fallback}",
        base_url=args.base_url, admin_key=args.admin_key)
    print(f"Set fallback for {args.name} -> {args.fallback}")


def cmd_key_add(args):
    result = _request("POST", "/admin/keys", {"name": args.name,
        "models": args.models.split(",") if args.models else None},
        args.base_url, args.admin_key)
    print(f"Added key: {result['name']}")
    print(f"API Key: {result['key']}")
    print(f"Hash: {result['hash']}")


def cmd_key_list(args):
    result = _request("GET", "/admin/keys", base_url=args.base_url, admin_key=args.admin_key)
    for k in result["data"]:
        print(f"  {k['name']:20s} {k['key_hash'][:16]}... models={k.get('models', 'all')}")
    if not result["data"]:
        print("  (no keys)")


def cmd_key_revoke(args):
    _request("DELETE", f"/admin/keys/{args.name}", base_url=args.base_url, admin_key=args.admin_key)
    print(f"Revoked key: {args.name}")


def cmd_stats(args):
    params = []
    if args.since: params.append(f"since={args.since}")
    if args.until: params.append(f"until={args.until}")
    params.append(f"group_by={args.group_by}")
    result = _request("GET", f"/admin/stats?{'&'.join(params)}", base_url=args.base_url, admin_key=args.admin_key)
    summary = result.get("summary", {})
    details = result.get("details", [])
    time_str = " ".join(filter(None, [f"since {args.since}" if args.since else None, f"until {args.until}" if args.until else None])) or "all time"
    print(f"\n=== Usage Statistics ({time_str}) ===\n")
    if summary.get("total_requests"):
        print(f"Total: {summary['total_requests']} requests, {summary['total_prompt_tokens'] or 0} prompt + {summary['total_completion_tokens'] or 0} completion = {summary['total_tokens'] or 0} tokens\n")
    if details:
        print(f"{'Name':25s} {'Requests':>10s} {'Prompt':>12s} {'Completion':>12s} {'Total':>12s}")
        print("-" * 75)
        for row in details:
            name = row["name"] or "(unknown)"
            print(f"{name:25s} {row['request_count']:10d} {row['prompt_tokens'] or 0:12d} {row['completion_tokens'] or 0:12d} {row['total_tokens'] or 0:12d}")
    else:
        print("  (no usage data)")


def build_parser():
    parser = argparse.ArgumentParser(prog="llm-admin", description="LLM Proxy Admin CLI")
    parser.add_argument("--config", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--admin-key", default=None)
    sub = parser.add_subparsers(dest="command")
    m = sub.add_parser("model")
    ms = m.add_subparsers(dest="action")
    p = ms.add_parser("add")
    p.add_argument("--id", required=True)
    p.add_argument("--provider", required=True, choices=["openai", "anthropic"])
    p.add_argument("--api-base", required=True)
    p.add_argument("--api-key", required=True)
    p.add_argument("--model-name", required=True)
    p.add_argument("--rpm", type=int, default=120)
    p.set_defaults(func=cmd_model_add)
    p = ms.add_parser("list")
    p.set_defaults(func=cmd_model_list)
    p = ms.add_parser("remove")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_model_remove)
    g = sub.add_parser("group")
    gs = g.add_subparsers(dest="action")
    p = gs.add_parser("add")
    p.add_argument("--name", required=True)
    p.add_argument("--models", required=True)
    p.add_argument("--weights", required=True)
    p.add_argument("--fallback", default=None)
    p.set_defaults(func=cmd_group_add)
    p = gs.add_parser("list")
    p.set_defaults(func=cmd_group_list)
    p = gs.add_parser("remove")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_group_remove)
    p = gs.add_parser("set-fallback")
    p.add_argument("--name", required=True)
    p.add_argument("--fallback", required=True)
    p.set_defaults(func=cmd_group_set_fallback)
    k = sub.add_parser("key")
    ks = k.add_subparsers(dest="action")
    p = ks.add_parser("add")
    p.add_argument("--name", required=True)
    p.add_argument("--models", default=None)
    p.set_defaults(func=cmd_key_add)
    p = ks.add_parser("list")
    p.set_defaults(func=cmd_key_list)
    p = ks.add_parser("revoke")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_key_revoke)
    s = sub.add_parser("stats")
    s.add_argument("--since", default=None)
    s.add_argument("--until", default=None)
    s.add_argument("--group-by", choices=["model", "provider", "group"], default="model")
    s.set_defaults(func=cmd_stats)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    config = _load_config(args.config)
    args.base_url = args.base_url or config.get("base_url", "http://localhost:4001")
    args.admin_key = args.admin_key or config.get("admin_key", "")
    if not args.admin_key:
        print("Error: --admin-key is required", file=sys.stderr)
        sys.exit(1)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
