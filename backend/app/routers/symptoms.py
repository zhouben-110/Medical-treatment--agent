from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas import SymptomListResponse, SymptomCategoryResponse
from app.models import SymptomCategory, Symptom

router = APIRouter()


@router.get("/symptoms", response_model=SymptomListResponse)
async def get_symptoms(db: AsyncSession = Depends(get_db)):
    """获取症状列表（无需认证）"""
    result = await db.execute(select(SymptomCategory))
    categories = result.scalars().all()

    response = []
    for category in categories:
        symptoms_result = await db.execute(
            select(Symptom).where(Symptom.category_id == category.id)
        )
        symptoms = symptoms_result.scalars().all()
        response.append(SymptomCategoryResponse(
            name=category.name,
            symptoms=[s.name for s in symptoms]
        ))

    return SymptomListResponse(categories=response)
