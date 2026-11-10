"""Serve, issue operator credentials, or drain the native durable delivery worker."""

from __future__ import annotations

import argparse
import asyncio

from notification_center.trusted.app import create_app
from notification_center.trusted.service import TrustedPublication
from quadkit.serialization import dumps_str
from quadkit.web.server.runner import run_server_async


async def run() -> None:
    """Explicit commands; no public registration, send or worker-control route."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["serve", "issue", "flush", "worker", "redrive"]
    )
    parser.add_argument("--email")
    parser.add_argument("--delivery-id")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--publisher", action="store_true")
    args = parser.parse_args()
    if args.command == "issue" and not args.email:
        parser.error("issue requires --email")
    if args.command == "redrive" and not args.delivery_id:
        parser.error("redrive requires --delivery-id")
    app = create_app()
    await app.start()
    try:
        service = await app.container.resolve(TrustedPublication)
        if args.command == "serve":
            await run_server_async(app)
        elif args.command == "issue":
            user = await service.users.get_user_by_email(args.email)
            if user is None:
                if not args.create:
                    parser.error(
                        "Account does not exist; use explicit --create to enroll it"
                    )
                user = await service.users.create_user(
                    args.email,
                    args.email,
                    None,
                    permissions=["editorial:publish"] if args.publisher else [],
                )
            elif args.publisher:
                parser.error("Existing permissions are not changed by token issuance")
            if user.is_active is not True:
                parser.error("Account is inactive")
            print(
                dumps_str(
                    {
                        "user_id": user.user_id,
                        "access_token": service.tokens.create_access_token(user),
                    }
                )
            )
        elif args.command == "flush":
            print(dumps_str({"delivered": await service.flush()}))
        elif args.command == "redrive":
            print(dumps_str({"delivery_id": await service.redrive(args.delivery_id)}))
        else:
            while True:
                await service.flush()
                await asyncio.sleep(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
