"""Cognee Cloud sync for the Mnemos NPC Brain.

The local graph (graph.py) is the deterministic source of truth for gameplay
math (trust weights, rumor propagation, dispositions). In parallel, every event
is mirrored into Cognee Cloud so the town's memory genuinely lives in Cognee and
can be queried semantically -- this is the "powered by Cognee" layer.

Activated only when COGNEE_API_KEY is set and the cognee SDK is installed. Every
call is best-effort: if Cognee is unavailable, the game keeps working on the
local graph and simply skips the cloud mirror.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any

logger = logging.getLogger("mnemos.cognee")


def _run(coro: Any) -> Any:
    """Run an async Cognee call from sync code, always returning a real result."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None or not loop.is_running():
        return asyncio.run(coro)
    result: dict[str, Any] = {}

    def _worker() -> None:
        result["v"] = asyncio.run(coro)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    return result.get("v")


class CogneeCloudSync:
    """Best-effort mirror of Mnemos memory into Cognee Cloud."""

    def __init__(self, api_key: str, dataset: str = "mnemos") -> None:
        self.dataset = dataset
        self.enabled = False
        self._buffer: list[str] = []
        self._flush_lock = threading.Lock()
        self._flushing = False
        try:
            import cognee

            # Cognee Cloud auth: the SDK talks to the hosted service when given
            # the cloud API key.
            try:
                cognee.config.set_llm_api_key(api_key)
            except Exception:  # noqa: BLE001
                os.environ.setdefault("COGNEE_API_KEY", api_key)
            self._cognee = cognee
            self.enabled = True
            logger.info("Cognee Cloud sync enabled (dataset=%s)", dataset)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cognee Cloud unavailable, running local-only: %r", exc)
            self._cognee = None

    @classmethod
    def from_env(cls, dataset: str = "mnemos") -> "CogneeCloudSync | None":
        key = os.environ.get("COGNEE_API_KEY")
        if not key:
            return None
        sync = cls(key, dataset=dataset)
        return sync if sync.enabled else None

    # -- write path ----------------------------------------------------------
    def remember(self, text: str) -> None:
        """Buffer a natural-language memory to mirror into Cognee."""
        if not self.enabled:
            return
        self._buffer.append(text)

    def flush(self, block: bool = False) -> dict:
        """Mirror buffered memories into Cognee Cloud.

        Fire-and-forget by default: the local typed graph is the authoritative
        source of truth for gameplay, so the cloud mirror must NEVER block a
        game turn (a cognify() call can take tens of seconds or hang if the
        network/LLM is slow). We drain the buffer synchronously and hand the
        heavy work to a daemon thread. Pass ``block=True`` (e.g. in tooling)
        to wait for completion.
        """
        if not self.enabled or not self._buffer:
            return {"flushed": 0}
        texts = list(self._buffer)
        self._buffer.clear()
        combined = "\n\n".join(texts)

        def _work() -> None:
            async def _do():
                await self._cognee.add(combined, dataset_name=self.dataset)
                await self._cognee.cognify(datasets=[self.dataset])

            try:
                _run(_do())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cognee flush failed (non-fatal): %r", exc)
            finally:
                self._flushing = False

        if block:
            _work()
            return {"flushed": len(texts)}

        # non-blocking: skip if a mirror is already in flight (buffer stays
        # drained; the next flush will carry any new memories).
        with self._flush_lock:
            if self._flushing:
                # re-queue these texts so they aren't lost
                self._buffer[:0] = texts
                return {"flushed": 0, "queued": len(texts)}
            self._flushing = True
        threading.Thread(target=_work, daemon=True).start()
        return {"flushed": len(texts), "async": True}

    def _flush_blocking(self) -> dict:
        """Legacy synchronous flush (kept for explicit tooling use)."""
        if not self.enabled or not self._buffer:
            return {"flushed": 0}
        texts = list(self._buffer)
        self._buffer.clear()
        combined = "\n\n".join(texts)

        async def _do():
            await self._cognee.add(combined, dataset_name=self.dataset)
            await self._cognee.cognify(datasets=[self.dataset])

        try:
            _run(_do())
            return {"flushed": len(texts)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cognee flush failed (non-fatal): %r", exc)
            return {"flushed": 0, "error": str(exc)}

    # -- read path -----------------------------------------------------------
    def recall(self, query: str) -> list[str]:
        """Semantic recall from Cognee Cloud (flavor/narration). Best-effort."""
        if not self.enabled:
            return []

        async def _do():
            fn = getattr(self._cognee, "search", None)
            if fn is None:
                return []
            try:
                return await fn(query_text=query)
            except TypeError:
                return await fn(query)

        try:
            raw = _run(_do())
            return [r if isinstance(r, str) else str(r) for r in (raw or [])]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cognee recall failed (non-fatal): %r", exc)
            return []

    # -- forget --------------------------------------------------------------
    def forget(self, text_hint: str) -> None:
        """Best-effort prune. Cognee's surgical delete API varies by version;
        the authoritative surgical forget happens on the local graph."""
        if not self.enabled:
            return

        async def _do():
            try:
                if hasattr(self._cognee, "delete"):
                    await self._cognee.delete(text_hint, dataset_name=self.dataset)
            except Exception:  # noqa: BLE001
                pass

        try:
            _run(_do())
        except Exception as exc:  # noqa: BLE001
            logger.debug("Cognee forget best-effort failure: %r", exc)
