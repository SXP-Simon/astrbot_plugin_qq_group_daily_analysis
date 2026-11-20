"""将本次绘图请求实际携带的角色参考图与分镜主角对应起来。"""

from typing import TypedDict

from ...shared.trace_context import TraceContext


class _ComicDrawingRequest(TypedDict):
    """最后一次漫画绘图请求的诊断记录。"""

    prompt: str
    reference_images_count: int


def format_character_prompt(scene: str, reference_count: int) -> str:
    """根据已经选入请求的图片补充绘图指令，分镜正文仍可单独用于文生图。

    Args:
        scene: 原始或重写后的分镜正文。
        reference_count: 此次交给绘图后端的角色参考图数量。

    Returns:
        有图时强调参考图优先于文字外貌；无图时原样返回分镜正文。

    Raises:
        无。
    """
    if reference_count:
        subject = "image shows" if reference_count == 1 else "images show"
        scene = (
            f"The attached {subject} the recurring protagonist of this comic. "
            "In every panel, match the face, hairstyle, hair colors, and recognizable "
            "outfit details to the visual reference, even if the scene text differs. "
            "Use the reference for character identity only. Follow the panel scenes "
            f"and render only the text explicitly specified below.\n\n{scene}"
        )
    if trace := TraceContext.current():
        request: _ComicDrawingRequest = {
            "prompt": scene,
            "reference_images_count": reference_count,
        }
        trace.metadata["last_comic_drawing_request"] = request
    return scene
