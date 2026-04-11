"""CLI entry point for Southview OCR.

Usage:
    python -m southview serve          — Start the API server
    python -m southview upload <path>  — Upload a video
    python -m southview process <id>   — Process a video
    python -m southview bakeoff ...    — Run/summarize model bake-off
    python -m southview export [opts]  — Export data
    python -m southview backup         — Create a backup
    python -m southview hash-password  — Generate a password hash
"""

import argparse
import sys


def _run_bakeoff_command(argv: list[str]) -> None:
    from southview.ocr.bakeoff import ALL_MODEL_IDS, run_bakeoff, summarize_bakeoff

    parser = argparse.ArgumentParser(
        prog="python -m southview bakeoff",
        description="Run or summarize Southview OCR model bake-off results.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run model bake-off on a curated card manifest and write CSV/summary artifacts.",
    )
    run_parser.add_argument("--manifest", required=True, help="Path to manifest CSV")
    run_parser.add_argument("--out-dir", required=True, help="Output directory for bake-off artifacts")
    run_parser.add_argument(
        "--models",
        nargs="+",
        default=ALL_MODEL_IDS,
        help="Optional model list override.",
    )

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Recompute summary metrics from an existing bake-off run and adjudication file.",
    )
    summarize_parser.add_argument("--run-dir", required=True, help="Bake-off run directory")
    summarize_parser.add_argument(
        "--adjudication",
        required=True,
        help="Adjudication CSV with human_name_correct/human_dod_correct overrides.",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "run":
        result = run_bakeoff(
            manifest_path=args.manifest,
            out_dir=args.out_dir,
            model_ids=list(args.models),
        )
        print("Bake-off complete.")
        print(f"predictions: {result['predictions_csv']}")
        print(f"adjudication: {result['adjudication_csv']}")
        print(f"summary json: {result['summary_json']}")
        print(f"summary md: {result['summary_md']}")
        return

    result = summarize_bakeoff(run_dir=args.run_dir, adjudication_path=args.adjudication)
    print("Bake-off summary updated.")
    print(f"summary json: {result['summary_json']}")
    print(f"summary md: {result['summary_md']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "serve":
        import uvicorn
        from southview.config import get_config

        config = get_config()
        api_config = config.get("api", {})
        uvicorn.run(
            "southview.api.app:create_app",
            factory=True,
            host=api_config.get("host", "0.0.0.0"),
            port=api_config.get("port", 8000),
            reload=False,
        )

    elif command == "upload":
        if len(sys.argv) < 3:
            print("Usage: python -m southview upload <video_path>")
            sys.exit(1)
        from southview.db.engine import init_db
        from southview.ingest.video_upload import upload_video

        init_db()
        video = upload_video(sys.argv[2])
        print(f"Video uploaded: id={video.id}, filename={video.filename}")

    elif command == "process":
        if len(sys.argv) < 3:
            print("Usage: python -m southview process <video_id>")
            sys.exit(1)
        from southview.db.engine import init_db
        from southview.jobs.manager import create_job
        from southview.jobs.runner import run_full_pipeline

        init_db()
        video_id = sys.argv[2]
        job = create_job(video_id, "full_pipeline")
        print(f"Job created: {job.id}")
        run_full_pipeline(job.id, video_id)
        print("Processing complete.")

    elif command == "bakeoff":
        _run_bakeoff_command(sys.argv[2:])

    elif command == "export":
        from southview.db.engine import init_db
        from southview.export.exporter import export_csv, export_json

        init_db()
        fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"
        if fmt == "json":
            output = export_json()
            print(output)
        else:
            output = export_csv()
            print(output)

    elif command == "backup":
        from southview.db.engine import init_db
        from southview.backup.backup_manager import create_backup

        init_db()
        path = create_backup()
        print(f"Backup created: {path}")

    elif command == "hash-password":
        import getpass

        from southview.auth import hash_password

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match.")
            sys.exit(1)
        print(hash_password(password))

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
