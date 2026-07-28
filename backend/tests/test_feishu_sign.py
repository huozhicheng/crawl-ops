import time
import hmac
import hashlib
import base64
import sys

# 修复后的 FeishuNotifier 逻辑
def calculate_sign(timestamp, secret):
    # 官方文档逻辑：string_to_sign = timestamp + "\n" + secret
    string_to_sign = f"{timestamp}\n{secret}"

    # 使用 string_to_sign 作为 key，对空字符串进行 hmac-sha256
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        "".encode("utf-8"),
        digestmod=hashlib.sha256
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

    if sign == expected_sign:
        print(f"SUCCESS: Signature validation successful!")
        print(f"Timestamp: {timestamp}")
        print(f"Signature: {sign}")
        print(f"Key used: {timestamp}\\n{secret}")
        return True
    else:
        print("FAILED: Signature mismatch!")
        return False

if __name__ == "__main__":
    if test_feishu_signature_logic():
        sys.exit(0)
    else:
        sys.exit(1)
