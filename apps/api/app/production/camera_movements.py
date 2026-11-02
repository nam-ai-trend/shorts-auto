from typing import Any
from pydantic import BaseModel, Field


class CameraMovementItem(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    best_for: list[str]
    prompt_syntax: str
    example_prompt: str


# aicameramovements.com 기반 유튜브 쇼츠 특화 핵심 12대 카메라 모션 라이브러리
CORE_CAMERA_MOVEMENTS: list[CameraMovementItem] = [
    CameraMovementItem(
        id="crash_zoom_in",
        name="Crash Zoom In",
        category="⚡ 임팩트 & 반전",
        summary="충격적인 팩트 발표나 상식 충돌 순간, 피사체로 매우 빠르고 강력하게 급접근",
        best_for=["0~3초 상식 충돌 후킹", "충격적인 수치 공개", "극적 반전 및 위기 순간"],
        prompt_syntax="camera: crash zoom in. movement: snap the lens rapidly toward {subject}. speed: very fast and punchy. framing: keep {subject} readable through the sudden scale change. end: land on a bold tight composition.",
        example_prompt="camera: crash zoom in. movement: snap the lens rapidly toward the miniature character's face. speed: very fast and punchy. framing: keep eyes readable through sudden scale change. end: land on an intense close-up with dramatic lighting.",
    ),
    CameraMovementItem(
        id="whip_pan",
        name="Whip Pan",
        category="⚡ 임팩트 & 반전",
        summary="신속한 수평 채찍 회전과 순간적 모션 블러로 국면 전환이나 다음 장소로 순간 이동",
        best_for=["'그런데 여기서 반전이...'", "장면/환경의 급격한 전환", "비교 대조 컷"],
        prompt_syntax="camera: whip pan {direction}. movement: rotate rapidly from {start_target} toward {end_target}. speed: fast snap with brief motion blur during rotation. framing: begin on one readable composition and land on a second readable target. end: settle into a sharp final frame.",
        example_prompt="camera: whip pan right. movement: rotate rapidly from the miniature lab table toward the open stormy window. speed: fast snap with brief motion blur. framing: start clear, sweep dynamically. end: settle on the lightning struck horizon.",
    ),
    CameraMovementItem(
        id="slow_zoom_in",
        name="Slow Zoom In (Dolly In)",
        category="🔍 긴장감 & 몰입",
        summary="호기심과 긴장감을 서서히 끌어올리며 피사체의 핵심 부위나 미세 원리로 점진적 접근",
        best_for=["호기심 유발 및 질문 단계", "미세한 과학적 메커니즘 관찰", "비밀스러운 단서 포커스"],
        prompt_syntax="camera: slow dolly in. movement: smoothly move the camera physically forward toward {subject}. speed: gradual and even. framing: keep {subject} centered as surrounding background softly blurs. end: finish on a stable intimate close-up.",
        example_prompt="camera: slow dolly in. movement: smoothly move forward toward the tiny clay crystal structure. speed: gradual and even. framing: keep microscopic facet centered. end: finish on a tactile macro close-up with soft creamy bokeh.",
    ),
    CameraMovementItem(
        id="slow_zoom_out",
        name="Slow Zoom Out (Dolly Out)",
        category="🔍 긴장감 & 몰입",
        summary="숨겨진 실체나 주변 환경의 실체를 서서히 드러내며 시야 확장",
        best_for=["'사실은 이렇습니다' 실체 규명", "전체 구조 및 관계성 제시", "반전의 전말 공개"],
        prompt_syntax="camera: slow dolly out. movement: smoothly move the camera physically backward away from {subject}. speed: gradual and even. framing: keep {subject} readable while more surrounding environment appears. end: finish on an expansive stable wider composition.",
        example_prompt="camera: slow dolly out. movement: move backward away from the single leaf. speed: gradual and even. framing: leaf stays clear as the towering tree branch appears. end: finish on a wide composition revealing the giant canopy.",
    ),
    CameraMovementItem(
        id="orbit",
        name="360 Orbit",
        category="🌀 3D 입체감 & 관찰",
        summary="피사체 주위를 360도 원형으로 회전하여 3D 볼륨감과 피사체 질감을 극대화",
        best_for=["쇼츠 특유의 입체 오브젝트 쇼케이스", "사물의 3차원 구조 설명", "주인공 캐릭터 탐색"],
        prompt_syntax="camera: circular orbit {direction}. movement: smoothly circle around {subject} along a curved 360-degree trajectory while maintaining focus. speed: smooth steady orbit. framing: keep {subject} locked at center with shifting background parallax. end: settle into a clean angled composition.",
        example_prompt="camera: circular orbit clockwise. movement: smoothly circle around the floating miniature gear mechanism. speed: smooth steady orbit. framing: gear locked at center with shifting studio lighting. end: settle into a three-quarter hero angle.",
    ),
    CameraMovementItem(
        id="arc_shot",
        name="Arc Shot",
        category="🌀 3D 입체감 & 관찰",
        summary="얕은 곡선 궤적으로 돌아가 피사체의 측면과 뒷배경의 깊이감(시차) 강조",
        best_for=["부드러운 시선 전환", "피사체와 배경의 거리감 연출", "감성적이거나 지적인 모멘트"],
        prompt_syntax="camera: shallow arc {direction}. movement: glide on a shallow curved path around {subject}. speed: smooth continuous gliding motion. framing: dynamic depth and parallax between {subject} and background. end: finish on an angled side perspective.",
        example_prompt="camera: shallow arc left. movement: glide on a shallow curve around the scientist figurine. speed: smooth gliding motion. framing: parallax between figurine and background chalkboard. end: finish on a side profile looking at the beaker.",
    ),
    CameraMovementItem(
        id="tracking_shot",
        name="Tracking / Follow Shot",
        category="🚀 역동성 & 추적",
        summary="움직이는 피사체, 물질, 액체의 이동 경로를 일정 거리를 유지하며 역동적으로 추적",
        best_for=["이동하는 물질이나 화학 반응 추적", "캐릭터의 달리기/이동", "생생한 액션감 부여"],
        prompt_syntax="camera: tracking follow shot. movement: travel smoothly through the scene tracking directly with {subject}. speed: match subject velocity evenly. framing: maintain consistent framing alongside or behind {subject}. end: follow subject to their final resting position.",
        example_prompt="camera: tracking follow shot. movement: travel smoothly alongside the miniature water drop rolling down a leaf. speed: match water droplet velocity evenly. framing: maintain sharp macro focus on droplet surface. end: finish as droplet drops off tip.",
    ),
    CameraMovementItem(
        id="low_tracking",
        name="Low-angle Tracking",
        category="🚀 역동성 & 추적",
        summary="바닥에 바짝 붙은 로우 앵글로 피사체를 거대하고 웅장하게 위압감 있게 연출",
        best_for=["거대한 팩트의 위압감 체감", "바닥에서 일어나는 미세한 사건", "영웅적이고 당당한 피사체"],
        prompt_syntax="camera: low-angle ground tracking. movement: glide forward at ground level looking upward toward {subject}. speed: smooth low sweeping glide. framing: low angle emphasizing grand scale and towering presence. end: come to rest looking up at {subject}.",
        example_prompt="camera: low-angle ground tracking. movement: glide forward along the floor looking up at the miniature skyscraper model. speed: smooth low sweep. framing: extreme upward angle emphasizing towering height. end: arrive at building base looking upward.",
    ),
    CameraMovementItem(
        id="push_past",
        name="Push Past (Pass-by)",
        category="🚀 역동성 & 추적",
        summary="전경 피사체를 스쳐 지나가며 뒤쪽의 새로운 광경이나 다음 씬 오브젝트를 연속성 있게 노출",
        best_for=["씬과 씬 사이의 완벽한 원테이크 인계", "장애물을 뚫고 새로운 세계로 진입", "자연스러운 시선 이동"],
        prompt_syntax="camera: push past / pass-by shot. movement: move smoothly forward directly past {foreground_subject} into the space behind. speed: continuous forward travel. framing: {foreground_subject} brushes past the frame edge, revealing the space behind. end: clear of foreground, landing directly on {background_subject}.",
        example_prompt="camera: push past. movement: move forward smoothly directly past the stone archway into the vibrant miniature forest. speed: continuous forward travel. framing: archway brushes past frame edge revealing colorful trees. end: clear of stone, framing the glowing center flower.",
    ),
    CameraMovementItem(
        id="pedestal_up",
        name="Pedestal Up (Crane Up)",
        category="🏔️ 스케일 & 공간감",
        summary="카메라 각도를 고정한 채 수직으로 상승하여 거대한 높이나 숨겨진 스케일을 공개",
        best_for=["밑바닥에서 정상까지의 높이 체감", "체감 수치 환산(에베레스트, 고층 등)", "상승하는 에너지/압력 묘사"],
        prompt_syntax="camera: vertical pedestal up. movement: lift the entire camera straight upward vertically without tilting. speed: smooth constant ascent. framing: travel vertically upward revealing towering vertical scale from base to top. end: land steadily on the upper climax view.",
        example_prompt="camera: vertical pedestal up. movement: lift camera straight upward vertically without tilting. speed: smooth constant ascent. framing: ascend from the ground along the giant clay thermometer. end: land steadily at the boiling red climax marker at top.",
    ),
    CameraMovementItem(
        id="drone_pull_back",
        name="Drone Pull Back",
        category="🏔️ 스케일 & 공간감",
        summary="빠르게 뒤로 멀어지며 주인공이 거대한 세계의 극히 일부임을 보여주는 압도적 스케일",
        best_for=["마지막 엔딩 클리프행어/펀치라인", "압도적 총량(조/억 단위) 체감", "거대한 자연/우주 스케일"],
        prompt_syntax="camera: aerial drone pull back. movement: fly smoothly backward and upward away from {subject}. speed: accelerating sweeping pull back. framing: {subject} rapidly shrinks into a vast, sprawling environment. end: majestic wide landscape revealing grand scale.",
        example_prompt="camera: aerial drone pull back. movement: fly smoothly backward and upward away from the lone character. speed: accelerating sweeping pull back. framing: character shrinks into an infinite ocean of clay dunes. end: majestic wide landscape revealing infinite scale.",
    ),
    CameraMovementItem(
        id="static_shot",
        name="Locked-off Static Shot",
        category="⏸️ 안정 & 디테일",
        summary="카메라를 삼각대에 고정하여 화면 내 복잡한 미세 움직임이나 텍스처 자체에 온전히 집중",
        best_for=["정밀한 분해/조립 과정", "텍스처와 형태의 정적인 아름다움", "복잡한 수치나 도표의 안정적 가독성"],
        prompt_syntax="camera: locked-off static shot. movement: hold one completely fixed camera position with zero camera drift. speed: completely still. framing: keep identical angle, height, lens distance, and composition. end: maintain stable framing throughout.",
        example_prompt="camera: locked-off static shot. movement: hold one fixed position for the full clip. speed: completely still and steady. framing: keep clay character and measuring scale perfectly centered. end: finish with the exact same stable composition.",
    ),
]

CORE_MOVEMENTS_MAP: dict[str, CameraMovementItem] = {
    m.id: m for m in CORE_CAMERA_MOVEMENTS
}


class MotionRecommendationItem(BaseModel):
    movement_id: str
    movement_name: str
    category: str
    reason: str
    suggested_video_prompt: str


class RecommendMotionResponse(BaseModel):
    scene_id: int
    narration: str
    current_motion_id: str | None = None
    recommendations: list[MotionRecommendationItem]
    available_movements: list[CameraMovementItem]

