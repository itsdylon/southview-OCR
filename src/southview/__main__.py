"""CLI entry point for Southview OCR.

Usage:
    python -m southview serve          - Start the API server
    python -m southview upload <path>  - Upload a video
    python -m southview process <id>   - Process a video
    python -m southview export [opts]  - Export data
    python -m southview backup         - Create a backup
    python -m southview hash-password  - Generate a password hash
"""

import sys


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
