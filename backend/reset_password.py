import asyncio
import sys
from sqlalchemy import select
from app.database import async_session
from app.models import User
from app.auth import hash_password

async def reset_password(email: str, new_password: str):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            print(f"[-] Error: 找不到邮箱为 {email} 的用户。")
            return
        user.hashed_password = hash_password(new_password)
        await session.commit()
        print(f"[+] Success: 已成功将用户 {email} 的密码重置为 {new_password}。")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("使用方法: python reset_password.py <邮箱> <新密码>")
    else:
        # Windows compatibility
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(reset_password(sys.argv[1], sys.argv[2]))
