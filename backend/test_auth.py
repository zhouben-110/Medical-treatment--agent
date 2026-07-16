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
    from app.auth import decode_supabase_token, hash_password, verify_password, create_access_token

    # 1. 测试密码哈希与验证
    password = "test-password-123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False
    print("[OK] 密码哈希与验证通过")

    # 2. 测试本地 JWT Token 生成与验证
    user_data = {"sub": "user-uuid-123", "email": "test@example.com"}
    token = create_access_token(user_data)
    payload = decode_supabase_token(token)
    assert payload.get("sub") == "user-uuid-123"
    assert payload.get("email") == "test@example.com"
    print("[OK] 本地 JWT 生成与解码验证通过")

    # 3. 测试无效 token
    try:
        decode_supabase_token("invalid-token")
        print("[FAIL] 应该拒绝无效 token")
    except Exception as e:
        print("[OK] 正确拒绝无效 token")


if __name__ == "__main__":
    print("=== 认证功能测试 ===\n")

    print("1. 测试配置...")
    config_ok = test_config()

    print("\n2. 测试 JWT 和密码哈希...")
    test_jwt_decode()

    print("\n=== 测试完成 ===")
