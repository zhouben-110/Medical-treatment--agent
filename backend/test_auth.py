"""测试认证功能"""

from app.config import get_settings

def test_config():
    """测试配置"""
    settings = get_settings()
    print("[OK] 配置加载成功")
    print(f"  - Supabase URL: {settings.supabase_url or '未配置'}")
    print(f"  - Supabase Anon Key: {'已配置' if settings.supabase_anon_key else '未配置'}")
    print(f"  - Supabase JWT Secret: {'已配置' if settings.supabase_jwt_secret else '未配置'}")
    return bool(settings.supabase_jwt_secret)

def test_jwt_decode():
    """测试 JWT 解码"""
    from app.auth import decode_supabase_token

    settings = get_settings()
    if not settings.supabase_jwt_secret:
        print("[SKIP] 跳过 JWT 测试：未配置 SUPABASE_JWT_SECRET")
        return

    # 测试无效 token
    try:
        decode_supabase_token("invalid-token")
        print("[FAIL] 应该拒绝无效 token")
    except Exception as e:
        print("[OK] 正确拒绝无效 token")

    print("\n提示：要测试有效 token，请使用前端登录后获取 token")

if __name__ == "__main__":
    print("=== 认证功能测试 ===\n")

    print("1. 测试配置...")
    config_ok = test_config()

    print("\n2. 测试 JWT 解码...")
    test_jwt_decode()

    print("\n=== 测试完成 ===")
    print("\n下一步：")
    print("1. 配置 Supabase 环境变量")
    print("2. 运行数据库迁移：python -m alembic upgrade head")
    print("3. 启动后端：python start.py")
    print("4. 启动前端：cd frontend && npm run dev")
    print("5. 访问 http://localhost:3000/register 注册用户")
