import asyncio
import hashlib

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import KBDocument


async def compile_kb() -> str:
    settings = get_settings()
    async with SessionLocal() as db:
        documents = list(
            (
                await db.scalars(
                    select(KBDocument)
                    .where(KBDocument.status == "approved")
                    .order_by(KBDocument.slug)
                )
            ).all()
        )
    blocks = []
    for document in documents:
        headings = " / ".join(filter(None, [document.title_en, document.title_es]))
        blocks.append(f"## {headings or document.slug}\n\n{document.body_md.strip()}")
    compiled = (
        "\n\n---\n\n".join(blocks)
        if blocks
        else "No company facts have been approved for this pilot yet."
    )
    version = hashlib.sha256(compiled.encode()).hexdigest()[:16]
    settings.kb_compiled_path.parent.mkdir(parents=True, exist_ok=True)
    settings.kb_compiled_path.write_text(compiled + "\n", encoding="utf-8")
    settings.kb_version_path.write_text(version + "\n", encoding="utf-8")
    return version


if __name__ == "__main__":
    print(asyncio.run(compile_kb()))
