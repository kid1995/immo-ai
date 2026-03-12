"""AI search agent – parses Vietnamese queries, searches listings, streams Vietnamese responses."""

import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.di_container import get_embedding
from core.logging import get_logger
from core.ports import LLMMessage, LLMPort
from core.schemas import ChatMessage
from services.agent import tools

log = get_logger(__name__)

_SYSTEM_PROMPT = """Bạn là trợ lý AI tìm kiếm bất động sản thương mại tại Đức cho người Việt Nam.

Nhiệm vụ:
- Hiểu câu hỏi tiếng Việt của người dùng
- Tìm kiếm danh sách bất động sản phù hợp
- Trả lời bằng tiếng Việt, rõ ràng và hữu ích
- Giải thích điểm số và đánh giá bằng tiếng Việt

Khi trả lời:
- Luôn nói giá bằng Euro (€)
- Giải thích các thuật ngữ tiếng Đức bằng tiếng Việt
- Mietpreis = tiền thuê hàng tháng
- Ablöse = phí chuyển nhượng
- Nebenkosten = chi phí phụ
- Kaution = tiền đặt cọc
- Flaeche = diện tích (m²)
- Erdgeschoss = tầng trệt
- Gewerbeimmobilie = bất động sản thương mại

Khi đánh giá cho tiệm nail:
- Cần có vòi nước (Wasseranschluss)
- Cần có hệ thống thông gió (Lüftung) vì hoá chất
- Tầng trệt là tốt nhất cho khách hàng đi bộ
- Ít đối thủ cạnh tranh trong bán kính 1km = tốt

Khi đánh giá cho nhà hàng:
- Cần có bếp (Küche)
- Cần có điện 3 pha (Starkstrom) cho bếp công nghiệp
- Diện tích lớn = nhiều chỗ ngồi = doanh thu cao hơn"""


class AgentService:
    def __init__(self, *, db: AsyncSession, llm: LLMPort) -> None:
        self._db = db
        self._llm = llm

    async def stream_response(
        self,
        messages: list[ChatMessage],
        branche: str = "nail",
    ) -> AsyncGenerator[str, None]:
        """Process user query: search listings, then stream Vietnamese response."""

        # 1. Parse user intent from the latest message
        user_message = messages[-1].content if messages else ""
        search_context = await self._gather_context(user_message, branche)

        # 2. Build full conversation with context
        llm_messages: list[LLMMessage] = []

        # Add conversation history
        for msg in messages[:-1]:
            llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

        # Add current message with search context
        augmented_content = (
            f"{user_message}\n\n"
            f"[Kết quả tìm kiếm / Search Results]:\n"
            f"{json.dumps(search_context, ensure_ascii=False, indent=2)}"
        )
        llm_messages.append(LLMMessage(role="user", content=augmented_content))

        # 3. Get LLM response
        response = await self._llm.complete(
            messages=llm_messages,
            system=_SYSTEM_PROMPT,
            max_tokens=2048,
        )

        # 4. Stream response in chunks
        content = response.content
        chunk_size = 50
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    async def _gather_context(self, query: str, branche: str) -> dict:
        """Search listings and gather context for the LLM."""
        context: dict = {"listings": [], "semantic": []}

        # SQL search – extract potential city/PLZ from query
        stadt = self._extract_city(query)
        sql_results = await tools.search_listings(
            self._db,
            stadt=stadt,
            branche=branche,
            limit=5,
        )
        context["listings"] = sql_results

        # Semantic search if embedding adapter is available
        try:
            embedding_port = get_embedding()
            query_embedding = await embedding_port.embed(query)
            semantic_results = await tools.semantic_search(
                self._db,
                query_embedding=query_embedding,
                limit=5,
            )
            context["semantic"] = semantic_results
        except Exception as exc:
            log.warning("semantic_search_skipped", error=str(exc))

        return context

    @staticmethod
    def _extract_city(query: str) -> str | None:
        """Simple city extraction from Vietnamese/German query."""
        german_cities = [
            "Berlin",
            "Hamburg",
            "München",
            "Köln",
            "Frankfurt",
            "Stuttgart",
            "Düsseldorf",
            "Dortmund",
            "Essen",
            "Leipzig",
            "Bremen",
            "Dresden",
            "Hannover",
            "Nürnberg",
            "Duisburg",
            "Bochum",
            "Wuppertal",
            "Bielefeld",
            "Bonn",
            "Münster",
            "Karlsruhe",
            "Mannheim",
            "Augsburg",
            "Wiesbaden",
            "Gelsenkirchen",
            "Mönchengladbach",
            "Braunschweig",
            "Chemnitz",
            "Kiel",
            "Aachen",
        ]
        query_lower = query.lower()
        for city in german_cities:
            if city.lower() in query_lower:
                return city
        return None
