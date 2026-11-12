import hashlib
import hmac
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from music.recommender import Recommender


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password = Column(String, nullable=False)
    genres = Column(String, default="[]", nullable=False)


class Event(Base):
    __tablename__ = "events"
    event_id = Column(String(36), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    track_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    event_time = Column(DateTime(timezone=True), index=True, nullable=False)
    source = Column(String, default="real", nullable=False)
    published = Column(Boolean, default=False, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    track_id = Column(String, primary_key=True)
    state = Column(String, nullable=False)


class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(100), nullable=False)


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    playlist_id = Column(String, ForeignKey("playlists.id"), primary_key=True)
    track_id = Column(String, primary_key=True)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class Preferences(BaseModel):
    genres: list[str] = Field(max_length=20)


class EventInput(BaseModel):
    event_id: uuid.UUID
    track_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["like", "dislike", "unlike", "open_spotify"]


class PlaylistInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
    return f"{salt}:{digest}"


def create_app(database_url=None, model_dir=None, secret_key=None):
    Path("data").mkdir(exist_ok=True)
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    engine = create_engine(database_url, connect_args={"check_same_thread": False}
                           if database_url.startswith("sqlite") else {})
    sessions = sessionmaker(engine, expire_on_commit=False)
    key = secret_key or os.getenv("SECRET_KEY")
    if not key or len(key) < 32:
        raise RuntimeError("Set SECRET_KEY to a random secret with at least 32 characters")
    signer = URLSafeTimedSerializer(key, salt="music-session-v1")
    security = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        app.state.recommender = Recommender(model_dir or os.getenv("MODEL_DIR", "artifacts/baseline"))
        yield
        engine.dispose()

    app = FastAPI(title="Music Insight", version="0.1.0", lifespan=lifespan)

    def db():
        with sessions() as session:
            yield session

    def current_user(credentials: HTTPAuthorizationCredentials = Depends(security), session=Depends(db)):
        try:
            if credentials is None:
                raise BadSignature("Missing token")
            user_id = signer.loads(credentials.credentials, max_age=86400)
        except (BadSignature, SignatureExpired):
            raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(401, "Tài khoản không tồn tại")
        return user

    def model():
        return app.state.recommender

    @app.get("/api/health")
    def health():
        return {"status": "ok", "tracks": len(model().tracks), "model": model().manifest["model_type"]}

    @app.post("/api/auth/register", status_code=201)
    def register(body: Credentials, session=Depends(db)):
        user = User(id=str(uuid.uuid4()), username=body.username.lower(), password=password_hash(body.password))
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "Tên đăng nhập đã tồn tại")
        return {"token": signer.dumps(user.id), "username": user.username}

    @app.post("/api/auth/login")
    def login(body: Credentials, session=Depends(db)):
        user = session.scalar(select(User).where(User.username == body.username.lower()))
        if user is None or not hmac.compare_digest(user.password, password_hash(body.password, user.password.split(":")[0])):
            raise HTTPException(401, "Sai tài khoản hoặc mật khẩu")
        return {"token": signer.dumps(user.id), "username": user.username}

    @app.get("/api/genres")
    def genres():
        return sorted({tag for tags in model().tracks.genres for tag in tags.split("|") if tag})

    @app.put("/api/me/preferences")
    def preferences(body: Preferences, user=Depends(current_user), session=Depends(db)):
        if set(body.genres) - set(genres()):
            raise HTTPException(422, "Thể loại không hợp lệ")
        user.genres = json.dumps(sorted(set(body.genres)))
        session.commit()
        return {"genres": json.loads(user.genres)}

    @app.get("/api/me")
    def me(user=Depends(current_user)):
        return {"username": user.username, "genres": json.loads(user.genres)}

    @app.get("/api/tracks")
    def tracks(q: str = Query(default="", max_length=100), limit: int = Query(default=30, ge=1, le=100)):
        frame = model().tracks
        match = frame.track_name.str.contains(q, case=False, regex=False) | frame.artists.str.contains(q, case=False, regex=False)
        indices = frame[match].sort_values("popularity", ascending=False).head(limit).index
        return model().records(indices)

    @app.get("/api/recommendations")
    def recommendations(limit: int = Query(default=20, ge=1, le=100), user=Depends(current_user), session=Depends(db)):
        feedback = session.scalars(select(Feedback).where(Feedback.user_id == user.id)).all()
        liked = [f.track_id for f in feedback if f.state == "like"]
        blocked = [f.track_id for f in feedback if f.state == "dislike"]
        return model().recommend(liked, blocked, json.loads(user.genres), limit)

    @app.post("/api/events", status_code=201)
    def event(body: EventInput, user=Depends(current_user), session=Depends(db)):
        if body.track_id not in model().index:
            raise HTTPException(404, "Không tìm thấy bài hát")
        event_id = str(body.event_id)
        existing = session.get(Event, event_id)
        if existing:
            if (existing.user_id, existing.track_id, existing.event_type) != (user.id, body.track_id, body.event_type):
                raise HTTPException(409, "event_id đã được dùng cho sự kiện khác")
            return {"event_id": event_id, "duplicate": True}
        session.add(Event(event_id=event_id, user_id=user.id, track_id=body.track_id,
                          event_type=body.event_type, event_time=datetime.now(timezone.utc)))
        if body.event_type in {"like", "dislike", "unlike"}:
            feedback = session.get(Feedback, (user.id, body.track_id))
            if feedback is None:
                session.add(Feedback(user_id=user.id, track_id=body.track_id, state=body.event_type))
            else:
                feedback.state = body.event_type
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "Xung đột cập nhật; thử lại với cùng event_id")
        return {"event_id": event_id, "duplicate": False}

    @app.get("/api/analytics/me")
    def analytics(user=Depends(current_user), session=Depends(db)):
        counts = session.execute(select(Event.event_type, func.count()).where(Event.user_id == user.id)
                                  .group_by(Event.event_type)).all()
        daily = session.execute(select(func.date(Event.event_time), func.count()).where(Event.user_id == user.id)
                                 .group_by(func.date(Event.event_time)).order_by(func.date(Event.event_time))).all()
        return {"counts": dict(counts), "daily": [{"date": str(day), "events": n} for day, n in daily],
                "note": "Tương tác của bạn trong ứng dụng; không phải lượt nghe Spotify"}

    @app.post("/api/playlists", status_code=201)
    def create_playlist(body: PlaylistInput, user=Depends(current_user), session=Depends(db)):
        playlist = Playlist(id=str(uuid.uuid4()), user_id=user.id, name=body.name)
        session.add(playlist)
        session.commit()
        return {"id": playlist.id, "name": playlist.name}

    @app.get("/api/playlists")
    def playlists(user=Depends(current_user), session=Depends(db)):
        result = []
        for playlist in session.scalars(select(Playlist).where(Playlist.user_id == user.id)):
            ids = session.scalars(select(PlaylistItem.track_id).where(PlaylistItem.playlist_id == playlist.id)).all()
            result.append({"id": playlist.id, "name": playlist.name,
                           "tracks": model().records([model().index[t] for t in ids if t in model().index])})
        return result

    @app.put("/api/playlists/{playlist_id}/tracks/{track_id}")
    def add_track(playlist_id: str, track_id: str, user=Depends(current_user), session=Depends(db)):
        playlist = session.get(Playlist, playlist_id)
        if playlist is None or playlist.user_id != user.id:
            raise HTTPException(404, "Playlist không tồn tại")
        if track_id not in model().index:
            raise HTTPException(404, "Bài hát không tồn tại")
        if session.get(PlaylistItem, (playlist_id, track_id)) is None:
            session.add(PlaylistItem(playlist_id=playlist_id, track_id=track_id))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "frontend", html=True), name="web")
    return app
