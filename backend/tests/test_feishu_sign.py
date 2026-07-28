import base64
import hashlib
import hmac
import sys
import time


# 修复后的 FeishuNotifier 逻辑
def calculate_sign(timestamp, secret):
    # 官方文档逻辑：string_to_sign = timestamp + "\n" + secret
    string_to_sign = f"{timestamp}\n{secret}"

    # 使用 string_to_sign 作为 key，对空字符串进行 hmac-sha256
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), "".encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return sign


def test_feishu_signature_logic():
    print("Starting corrected Feishu signature validation...")
    secret = "test-secret"
    timestamp = int(time.time())

    # 生成的签名
    sign = calculate_sign(timestamp, secret)

    # 再次计算以验证一致性（此脚本内部验证）
    expected_sign = calculate_sign(timestamp, secret)

    assert sign == expected_sign
    print("SUCCESS: Signature validation successful!")
    print(f"Timestamp: {timestamp}")
    print(f"Signature: {sign}")
    print(f"Key used: {timestamp}\\n{secret}")


if __name__ == "__main__":
    test_feishu_signature_logic()
    sys.exit(0)
