"""症状分类初始数据"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.schemas import SymptomCategory, Symptom

SYMPTOM_DATA = {
    "头部": ["头痛", "头晕", "耳鸣", "视力模糊", "鼻塞", "流涕"],
    "胸部": ["胸闷", "咳嗽", "气短", "心悸", "呼吸困难"],
    "腹部": ["腹痛", "腹泻", "便秘", "恶心", "呕吐", "胃胀"],
    "四肢": ["关节痛", "肌肉酸痛", "手脚麻木", "肿胀"],
    "全身": ["发热", "乏力", "失眠", "食欲不振", "体重变化"],
    "皮肤": ["皮疹", "瘙痒", "红肿", "脱皮"],
}


async def seed_symptoms():
    async with async_session() as session:
        for category_name, symptoms in SYMPTOM_DATA.items():
            category = SymptomCategory(name=category_name)
            session.add(category)
            await session.flush()
            for symptom_name in symptoms:
                symptom = Symptom(category_id=category.id, name=symptom_name)
                session.add(symptom)
        await session.commit()


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_symptoms())
