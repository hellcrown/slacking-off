# -*- coding: utf-8 -*-
"""人脸检测：YuNet（OpenCV 5 内置 FaceDetectorYN，模型文件在 models/ 下）。

模型来自官方 opencv_zoo 仓库（face_detection_yunet_2023mar.onnx，232KB），
本地推理，不上传任何画面。
"""
import os
import sys

import cv2
import numpy as np


def _resource_root() -> str:
    """只读资源根目录：打包后模型在 PyInstaller 解压目录(_MEIPASS)。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


MODEL_PATH = os.path.join(_resource_root(), "models", "face_detection_yunet_2023mar.onnx")


def _load_model_buffer() -> np.ndarray:
    """把模型读进内存。OpenCV 的 C++ 层读不了含非 ASCII 字符的文件路径
    （如中文用户名的 Temp 目录、中文安装目录），内存加载则完全不受路径影响。"""
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"未找到人脸模型文件: {MODEL_PATH}\n"
            "请从 opencv_zoo 下载 face_detection_yunet_2023mar.onnx 放入 models/ 目录"
        )
    return np.fromfile(MODEL_PATH, dtype=np.uint8)  # np.fromfile 支持任意 Unicode 路径


class FaceDetector:
    def __init__(self, score_threshold: float = 0.6, min_face_size: int = 80):
        self._det = cv2.FaceDetectorYN.create(
            "onnx", _load_model_buffer(), np.array([], dtype=np.uint8),
            (320, 320), score_threshold=score_threshold,
            nms_threshold=0.3, top_k=5000,
        )
        self._input_size = (0, 0)
        self.set_params(score_threshold, min_face_size)

    def set_params(self, score_threshold: float, min_face_size: int) -> None:
        # 阈值越低越灵敏（0.9=严格，0.5=敏感），默认 0.6
        self.score_threshold = min(0.95, max(0.1, float(score_threshold)))
        self.min_face_size = max(16, int(min_face_size))
        self._det.setScoreThreshold(self.score_threshold)

    def detect(self, frame_bgr: np.ndarray) -> np.ndarray:
        """返回人脸矩形数组 shape=(n,4)，每行 (x, y, w, h)。"""
        h, w = frame_bgr.shape[:2]
        if (w, h) != self._input_size:
            self._input_size = (w, h)
            self._det.setInputSize((w, h))
        _, faces = self._det.detect(frame_bgr)
        if faces is None or len(faces) == 0:
            return np.empty((0, 4), dtype=np.int32)
        boxes = faces[:, :4].astype(np.int32)          # x, y, w, h
        # 过滤太小的检测框（远处小误检）
        keep = boxes[:, 2] >= self.min_face_size
        return boxes[keep] if keep.any() else np.empty((0, 4), dtype=np.int32)

    @staticmethod
    def annotate(frame_bgr: np.ndarray, faces: np.ndarray) -> np.ndarray:
        """在帧上画出人脸框与人数，用于预览。"""
        out = frame_bgr.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        n = len(faces)
        color = (0, 0, 255) if n >= 2 else (0, 200, 0)
        cv2.putText(out, f"Faces: {n}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, color, 2)
        return out
