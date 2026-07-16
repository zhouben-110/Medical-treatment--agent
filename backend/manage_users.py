import asyncio
import sys
from sqlalchemy import select
from app.database import async_session
from app.models import User

async def list_users():
    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.created_at))
        users = result.scalars().all()
        print("\n=== 已注册用户列表 ===")
        print(f"{'ID':<38} | {'邮箱':<30} | {'角色':<10} | {'激活状态':<8}")
        print("-" * 96)
        for u in users:
            print(f"{u.id:<38} | {str(u.email):<30} | {u.role:<10} | {str(u.is_active):<8}")
        print(f"======================\n共计 {len(users)} 个用户\n")

async def delete_user(email: str):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            print(f"[-] 找不到邮箱为 {email} 的用户。")
            return
        await session.delete(user)
        await session.commit()
        print(f"[+] 已成功删除用户: {email}")

async def set_role(email: str, role: str):
    if role not in ("user", "admin"):
        print("[-] 角色必须为 'user' 或 'admin'")
        return
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            print(f"[-] 找不到邮箱为 {email} 的用户。")
            return
        user.role = role
        await session.commit()
        print(f"[+] 已成功将用户 {email} 的角色设置为 {role}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  1. 列出所有用户: python manage_users.py list")
        print("  2. 修改用户角色: python manage_users.py set-role <邮箱> <user/admin>")
        print("  3. 删除用户:     python manage_users.py delete <邮箱>")
        sys.exit(0)
        
    cmd = sys.argv[1].lower()
    if cmd == "list":
        asyncio.run(list_users())
    elif cmd == "delete" and len(sys.argv) >= 3:
        asyncio.run(delete_user(sys.argv[2]))
    elif cmd == "set-role" and len(sys.argv) >= 4:
        asyncio.run(set_role(sys.argv[2], sys.argv[3]))
    else:
        print("[-] 未知命令或缺少参数。")
