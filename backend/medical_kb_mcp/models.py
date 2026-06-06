import uuid
from sqlalchemy import String, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _gen_id() -> str:
    return str(uuid.uuid4())


class Disease(Base):
    __tablename__ = "diseases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_id)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    treatment: Mapped[str] = mapped_column(Text, default="")
    when_to_see_doctor: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String, default="")

    __table_args__ = (
        Index("ix_diseases_symptoms_gin", "symptoms", postgresql_using="gin"),
    )
