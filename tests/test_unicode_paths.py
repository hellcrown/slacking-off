# -*- coding: utf-8 -*-
"""回归测试：中文用户名/临时目录环境下模型加载（曾导致对方机器上点开始监测无反应）。

模拟：把 TMP/TEMP 指向含中文的目录（对应用户名"陈帅父亲"的场景），
旧代码会把模型复制到该目录再用 OpenCV 读（失败），新代码走内存加载不受影响。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHINESE_TMP = os.path.join(ROOT, "tests", "临时测试目录")
os.makedirs(CHINESE_TMP, exist_ok=True)

CODE = """
import sys
sys.path.insert(0, r"__ROOT__")
import numpy as np
from core.detector import FaceDetector, MODEL_PATH
import os
# 确认旧方案的痕迹不应存在：临时目录里不应再生成 sentinel_yunet*.onnx
tmp_files = [f for f in os.listdir(r"__TMP__") if f.startswith("sentinel_yunet")]
assert not tmp_files, "临时目录出现模型副本: %r" % tmp_files
det = FaceDetector()
img = (np.random.rand(320, 320, 3) * 255).astype(np.uint8)
faces = det.detect(img)
print("DETECT-OK faces:", len(faces))
""".replace("__ROOT__", ROOT).replace("__TMP__", CHINESE_TMP)

env = os.environ.copy()
env["TMP"] = CHINESE_TMP
env["TEMP"] = CHINESE_TMP
env["PYTHONIOENCODING"] = "utf-8"

r = subprocess.run([sys.executable, "-c", CODE], env=env,
                   capture_output=True, text=True, cwd=ROOT)
out = r.stdout + r.stderr
print(out.strip()[-800:])

os.rmdir(CHINESE_TMP)  # 空则删除（有残留副本会报错，正是要抓的）

assert r.returncode == 0 and "DETECT-OK" in out, "中文临时目录环境下加载失败"
print()
print("UNICODE PATH REGRESSION PASSED")
