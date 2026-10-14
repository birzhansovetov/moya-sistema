"""Bound archive upload bodies before Starlette parses multipart data."""

from app.backup_archive import MAX_ARCHIVE_BYTES


MAX_REQUEST_BYTES = MAX_ARCHIVE_BYTES + 64 * 1024  # multipart framing and fields
UPLOAD_PATHS = {"/api/profile/backup/preview", "/api/profile/backup/restore"}


class BackupUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope["path"] not in UPLOAD_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > MAX_REQUEST_BYTES:
            await self._reject(send)
            return

        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                await self._reject(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def _reject(send):
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": '{"detail":"Архив слишком большой"}'.encode("utf-8")})
