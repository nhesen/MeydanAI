import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.domain import Highlight, Match, Player, Team, User
from app.repositories.auth import AuthRepository
from app.repositories.processing import ProcessingRepository
from app.schemas.admin import (
    AdminDashboardResponse,
    HighlightUpdate,
    HighlightWrite,
    UserRoleUpdate,
)
from app.schemas.auth import UserResponse
from app.schemas.platform import PageResponse, PlatformHighlightResponse
from app.schemas.processing import ProcessingJobResponse
from app.services.audit import AuditService
from app.services.platform import PlatformService
from app.services.processing import ProcessingService


class AdminService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.processing_repository = ProcessingRepository(session)
        self.platform = PlatformService(session)
        self.processing = ProcessingService(session)
        self.audit = AuditService(session)

    def dashboard(self) -> AdminDashboardResponse:
        recent = self.platform.list_matches(
            query=None,
            status=None,
            team_id=None,
            date_from=None,
            date_to=None,
            page=1,
            page_size=5,
        )
        return AdminDashboardResponse(
            total_matches=self._count(Match),
            total_users=self._count(User),
            total_players=self._count(Player),
            total_teams=self._count(Team),
            failed_jobs=self.processing_repository.count_by_status("failed"),
            active_jobs=self.processing_repository.count_by_status("processing")
            + self.processing_repository.count_by_status("queued"),
            recent_matches=recent.items,
        )

    def list_users(
        self, *, query: str | None, page: int, page_size: int
    ) -> PageResponse[UserResponse]:
        filters = []
        if query:
            filters.append(User.email.ilike(f"%{query}%"))
        total = self.session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
        items = list(
            self.session.scalars(
                select(User)
                .where(*filters)
                .order_by(User.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return self._page(
            [UserResponse.model_validate(item) for item in items],
            page,
            page_size,
            total,
        )

    def update_user_role(
        self,
        user_id: uuid.UUID,
        payload: UserRoleUpdate,
        actor: User,
    ) -> UserResponse:
        user = self.auth_repository.get_user(user_id)
        if user is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="User was not found.",
                error_code="USER_NOT_FOUND",
            )
        if (
            user.role == "admin"
            and payload.role != "admin"
            and self.auth_repository.admin_count() <= 1
        ):
            raise DomainError(
                status=409,
                title="Conflict",
                detail="The last administrator cannot be demoted.",
                error_code="LAST_ADMIN_REQUIRED",
            )
        previous_role = user.role
        user.role = payload.role
        self.audit.record(
            actor_user_id=actor.id,
            action="user.role_change",
            entity_type="user",
            entity_id=str(user.id),
            metadata={"from": previous_role, "to": payload.role},
        )
        self.session.commit()
        return UserResponse.model_validate(user)

    def list_jobs(
        self,
        *,
        status: str | None,
        page: int,
        page_size: int,
    ) -> PageResponse[ProcessingJobResponse]:
        total, items = self.processing_repository.list_jobs_by_status(
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return self._page(
            [ProcessingService.to_response(item) for item in items],
            page,
            page_size,
            total,
        )

    def retry_job(self, job_id: uuid.UUID, user: User) -> ProcessingJobResponse:
        result = self.processing.retry_job(job_id, user=user)
        self.audit.record(
            actor_user_id=user.id,
            action="processing.retry",
            entity_type="processing_job",
            entity_id=str(job_id),
            metadata={"retry_job_id": str(result.id)},
            commit=True,
        )
        return result

    def create_highlight(self, payload: HighlightWrite, actor: User) -> PlatformHighlightResponse:
        match = self.session.get(Match, payload.match_id)
        if match is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="Match was not found.",
                error_code="MATCH_NOT_FOUND",
            )
        if payload.player_id is not None and self.session.get(Player, payload.player_id) is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="Player was not found.",
                error_code="PLAYER_NOT_FOUND",
            )
        highlight = Highlight(
            match_id=payload.match_id,
            player_id=payload.player_id,
            highlight_type=payload.highlight_type,
            timestamp_ms=payload.timestamp_ms,
            title=payload.title.strip(),
            video_url=payload.video_url,
            thumbnail_url=payload.thumbnail_url,
            duration_ms=payload.duration_ms,
        )
        self.session.add(highlight)
        self.session.flush()
        self.audit.record(
            actor_user_id=actor.id,
            action="highlight.create",
            entity_type="highlight",
            entity_id=str(highlight.id),
            metadata={"match_id": str(payload.match_id)},
        )
        self.session.commit()
        return self._highlight_response(highlight)

    def update_highlight(
        self,
        highlight_id: uuid.UUID,
        payload: HighlightUpdate,
        actor: User,
    ) -> PlatformHighlightResponse:
        highlight = self._require_highlight(highlight_id)
        if payload.player_id is not None and self.session.get(Player, payload.player_id) is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="Player was not found.",
                error_code="PLAYER_NOT_FOUND",
            )
        if payload.player_id is not None:
            highlight.player_id = payload.player_id
        if payload.highlight_type is not None:
            highlight.highlight_type = payload.highlight_type
        if payload.timestamp_ms is not None:
            highlight.timestamp_ms = payload.timestamp_ms
        if payload.title is not None:
            highlight.title = payload.title.strip()
        if payload.video_url is not None:
            highlight.video_url = payload.video_url
        if payload.thumbnail_url is not None:
            highlight.thumbnail_url = payload.thumbnail_url
        if payload.duration_ms is not None:
            highlight.duration_ms = payload.duration_ms
        self.audit.record(
            actor_user_id=actor.id,
            action="highlight.update",
            entity_type="highlight",
            entity_id=str(highlight.id),
        )
        self.session.commit()
        return self._highlight_response(highlight)

    def delete_highlight(self, highlight_id: uuid.UUID, actor: User) -> None:
        highlight = self._require_highlight(highlight_id)
        self.audit.record(
            actor_user_id=actor.id,
            action="highlight.delete",
            entity_type="highlight",
            entity_id=str(highlight.id),
        )
        self.session.delete(highlight)
        self.session.commit()

    def _require_highlight(self, highlight_id: uuid.UUID) -> Highlight:
        highlight = self.session.get(Highlight, highlight_id)
        if highlight is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="Highlight was not found.",
                error_code="HIGHLIGHT_NOT_FOUND",
            )
        return highlight

    def _highlight_response(self, highlight: Highlight) -> PlatformHighlightResponse:
        match = highlight.match
        if match is None:
            match = self.session.get(Match, highlight.match_id)
        player = highlight.player
        return PlatformHighlightResponse(
            id=highlight.id,
            match_id=highlight.match_id,
            match_title=match.title if match is not None else None,
            player_id=highlight.player_id,
            player_name=player.display_name if player is not None else None,
            highlight_type=highlight.highlight_type,
            timestamp_ms=highlight.timestamp_ms,
            title=highlight.title,
            video_url=highlight.video_url,
            thumbnail_url=highlight.thumbnail_url,
            duration_ms=highlight.duration_ms,
            created_at=highlight.created_at,
        )

    def _count(self, model: type[object]) -> int:
        return self.session.scalar(select(func.count()).select_from(model)) or 0

    @staticmethod
    def _page[T](items: list[T], page: int, page_size: int, total: int) -> PageResponse[T]:
        total_pages = (total + page_size - 1) // page_size if total else 0
        return PageResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )
