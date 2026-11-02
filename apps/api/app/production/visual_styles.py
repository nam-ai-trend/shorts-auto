from typing import Any
from pydantic import BaseModel, Field


class VisualStyleItem(BaseModel):
    id: str
    number: int
    name: str
    feature: str
    best_for: str
    icon: str
    system_persona: str
    image_prompt_guide: str
    default_concept_style: str
    sample_prompt_prefix: str


# 사용자 정의 10대 비주얼 스타일 카탈로그
VISUAL_STYLES: list[VisualStyleItem] = [
    VisualStyleItem(
        id="live_action",
        number=1,
        name="실사형 (Live Action)",
        feature="실제 사람, 사물, 배경을 촬영하거나 AI로 사실적으로 구현",
        best_for="과학 현상, 실험, 자연, 역사",
        icon="📸",
        system_persona="당신은 세계 최고의 다큐멘터리/실사 내셔널 지오그래픽 스타일 쇼츠 영상 디렉터이자 하이퍼리얼리즘 프롬프트 마스터입니다.",
        image_prompt_guide="""- 비주얼 스타일: 극사실주의 실사 다큐멘터리 사진 (Hyperrealistic, 8k documentary photography).
- 카메라 & 렌즈: 35mm 또는 macro photography lens, f/1.8 shallow depth of field, natural photorealistic bokeh.
- 조명 및 질감: 사실적인 자연광 또는 스튜디오 필라이트 (natural cinematic ambient daylight, authentic skin/material textures, true-to-life physical details).
- 텍스트 배제: Strictly NO text, NO letters, NO artificial CGI plastic gloss.""",
        default_concept_style="Hyperrealistic 8k live-action documentary photograph, authentic real-world textures, natural ambient lighting, 35mm lens macro detail, vertical 9:16 portrait",
        sample_prompt_prefix="Hyperrealistic 8k live-action documentary photograph, 35mm macro lens. [Scene subject details]. Authentic physical textures, natural cinematic lighting, vertical 9:16, strictly NO text, NO letters."
    ),
    VisualStyleItem(
        id="cinematic",
        number=2,
        name="시네마틱 (Cinematic)",
        feature="영화 같은 조명, 카메라 움직임, 극적인 연출",
        best_for="미스터리, 우주, 감동적인 이야기",
        icon="🎬",
        system_persona="당신은 할리우드 SF/드라마 블록버스터 영화 촬영 감독이자 시네마토그래퍼입니다.",
        image_prompt_guide="""- 비주얼 스타일: 할리우드 블록버스터 영화 스틸컷 (Epic cinematic movie still, anamorphic widescreen look adapted to 9:16).
- 조명 & 분위기: 극적인 키라이트, 볼류메트릭 갓레이, 짙은 림라이트, 필름 그레인 (dramatic chiaroscuro lighting, volumetric atmospheric fog/god rays, high-contrast rim light, 35mm film grain, moody cinematic atmosphere).
- 컬러 그레이딩: 블록버스터 틸앤오렌지 또는 묵직한 필름 톤 (cinematic color grade, deep shadows, rich dramatic tones).
- 텍스트 배제: Strictly NO text, NO subtitles, NO movie logos.""",
        default_concept_style="Epic cinematic movie still, dramatic chiaroscuro volumetric lighting, 35mm anamorphic lens, high contrast, atmospheric depth, vertical 9:16 portrait",
        sample_prompt_prefix="Epic cinematic movie still, shot on Arri Alexa 65. [Scene subject details]. Volumetric atmospheric rays, dramatic rim lighting, intense moody cinematic tone, vertical 9:16 portrait, strictly NO text."
    ),
    VisualStyleItem(
        id="2d_cartoon",
        number=3,
        name="2D 카툰 애니메이션",
        feature="평면 캐릭터와 일러스트가 움직이는 방식",
        best_for="과학 상식, 교육, 스토리텔링",
        icon="🎨",
        system_persona="당신은 글로벌 명작 2D 애니메이션(카툰 네트워크/디즈니 전통 2D 스타일)의 비주얼 아트 디렉터입니다.",
        image_prompt_guide="""- 비주얼 스타일: 세련되고 위트 있는 모던 2D 카툰 일러스트 (Clean vibrant 2D vector animation style, crisp line art, flat shaded with subtle cell highlights).
- 캐릭터 & 형태: 뚜렷하고 깔끔한 외곽선, 귀엽고 과장된 표정의 카툰 캐릭터 (charming stylized expressive cartoon characters, clean bold outlines).
- 색감: 밝고 경쾌한 고채도 컬러 팔레트 (vibrant playful color palette, pastel tones with punchy accents).
- 텍스트 배제: Strictly NO text, NO word bubbles, clean 2D vector art.""",
        default_concept_style="Vibrant clean modern 2D cartoon animation illustration, crisp bold outlines, expressive stylized characters, colorful cheerful palette, vertical 9:16 portrait",
        sample_prompt_prefix="Vibrant modern 2D cartoon animation style, clean vector linework. [Scene subject details]. Expressive playful character, flat cell shading, rich colorful palette, vertical 9:16, strictly NO text."
    ),
    VisualStyleItem(
        id="anime",
        number=4,
        name="애니메이션 / 일본 애니풍",
        feature="만화적인 인물, 배경, 표정과 역동적인 연출",
        best_for="역사, 가상 상황, 스토리형 쇼츠",
        icon="⚡",
        system_persona="당신은 신카이 마코토 및 유포테이블 스타일의 일본 극장판 애니메이션 비주얼 디렉터입니다.",
        image_prompt_guide="""- 비주얼 스타일: 현대 일본 고퀄리티 극장판 애니메이션 스틸 (High-end modern Japanese anime art style, Makoto Shinkai aesthetic, Kyoto Animation polish).
- 비주얼 요소: 섬세한 셀 셰이딩, 눈부신 자연광 렌즈 플레어, 파스텔 하늘과 감성적인 배경 디테일 (cel-shaded character illustration, glowing lens flare, highly detailed painted background, vibrant emotional atmosphere).
- 선화 & 디테일: 정교한 애니메이션 라인아트와 생동감 넘치는 눈동자/표정 디테일.
- 텍스트 배제: Strictly NO text, NO Japanese characters, NO manga sound effects.""",
        default_concept_style="High-end Japanese anime visual style, Makoto Shinkai aesthetic, glowing golden hour lens flare, highly detailed anime background, vertical 9:16 portrait",
        sample_prompt_prefix="High-end modern Japanese anime style, theatrical animation still. [Scene subject details]. Luminous sunlight, beautiful painted anime sky, delicate cel shading, vertical 9:16, strictly NO text."
    ),
    VisualStyleItem(
        id="3d_cgi",
        number=5,
        name="3D 애니메이션 (CGI)",
        feature="입체 모델과 가상 카메라를 이용한 영상",
        best_for="인체 내부, 기계 구조, 과학 원리",
        icon="💎",
        system_persona="당신은 픽사(Pixar)/드림웍스 3D 렌더링 및 과학 시각화 전문 CGI 슈퍼바이저입니다.",
        image_prompt_guide="""- 비주얼 스타일: 최첨단 3D CGI 애니메이션 (Pixar / Unreal Engine 5 high-end 3D CGI render).
- 렌더링 & 서페이스: 정밀한 서브서피스 스캐터링(SSS), 입체적인 매끄러운 3D 텍스처, 물리 기반 렌더링(PBR) (subsurface scattering, ray-traced reflections, clean stylized 3D geometry).
- 조명: 풍부한 스튜디오 3점 조명 및 반사광 (soft 3-point studio lighting, rim highlights, global illumination).
- 텍스트 배제: Strictly NO text, NO numbers, clean 3D render.""",
        default_concept_style="High-end Pixar-style 3D CGI animation render, subsurface scattering, ray-traced studio lighting, vibrant detailed stylized models, vertical 9:16 portrait",
        sample_prompt_prefix="High-end 3D CGI render, Pixar and Unreal Engine 5 aesthetic. [Scene subject details]. Smooth stylized textures, ray-traced studio rim lighting, vivid vibrant colors, vertical 9:16, strictly NO text."
    ),
    VisualStyleItem(
        id="motion_graphics",
        number=6,
        name="모션그래픽 (Motion Graphics)",
        feature="도형, 아이콘, 다이어그램, 숫자를 움직여 설명",
        best_for="AI, 기술, 공학, 정보 전달",
        icon="📊",
        system_persona="당신은 Vox / Kurzgesagt 스타일의 프리미엄 지식 인포그래픽 모션그래픽 디렉터입니다.",
        image_prompt_guide="""- 비주얼 스타일: 미래지향적이고 깔끔한 미니멀 벡터 인포그래픽 모션 그래픽 (Sleek tech motion graphics, isometric 3D / vector infographic diagrams, tech-minimalism).
- 구성 요소: 기하학적 도형, 추상 데이터 플로우, 테크 아이콘, 선명한 데이터 시각화 오브젝트 (geometric wireframes, glowing futuristic data nodes, clean abstract iconography, dark sleek backdrop).
- 색감 & 분위기: 다크 슬레이트 배경에 네온/시안/퍼플 포인트 액센트 (dark high-tech slate palette with glowing cyan and indigo accent glows).
- 텍스트 배제: Strictly NO fake text, NO unreadable gibberish labels, clean visual diagrams only.""",
        default_concept_style="Sleek modern motion graphics infographic, dark tech background, isometric geometric elements, clean glowing cyan/violet accents, vertical 9:16 portrait",
        sample_prompt_prefix="Sleek modern motion graphics infographic style, tech data visualization. [Scene subject details]. Geometric abstract nodes, isometric layout, clean dark aesthetic, vertical 9:16, strictly NO text."
    ),
    VisualStyleItem(
        id="kinetic_typography",
        number=7,
        name="키네틱 타이포그래피",
        feature="자막과 글자가 음성에 맞춰 확대·축소·이동",
        best_for="명언, 동기부여, 강렬한 정보 전달",
        icon="🔤",
        system_persona="당신은 강렬한 시각적 충격과 타이포 연출을 결합하는 익스트림 키네틱 타이포그래피 모션 디자이너입니다.",
        image_prompt_guide="""- 비주얼 스타일: 볼드하고 역동적인 타이포그래픽 아트 및 그래픽 포스터 (Bold brutalist kinetic graphic design, dynamic typography aesthetic, high-contrast poster art).
- 배경 & 무드: 미니멀하면서도 파괴적인 질감 (묵직한 콘크리트, 메탈릭 그라데이션, 미니멀 네거티브 스페이스, 스트로브 라이팅).
- 강조: 시각적 임팩트를 주는 강렬한 상징 오브젝트와 대담한 그래픽 심볼.
- 주의: AI 이미지 자체에는 철자 오류를 유발하는 복잡한 영문 텍스트를 배제하고, 강력한 시각적 앰비언트 그래픽과 중앙 상징물을 중심으로 생성 (clean bold graphic visual anchor).""",
        default_concept_style="Bold brutalist kinetic graphic design background, high-contrast monochrome with electric yellow accent, dramatic graphic poster aesthetic, vertical 9:16",
        sample_prompt_prefix="Bold graphic design poster style, brutalist typography aesthetic background. [Scene subject details]. High contrast, stark studio shadow, electric accent lighting, vertical 9:16, strictly NO letters."
    ),
    VisualStyleItem(
        id="claymation",
        number=8,
        name="스톱모션 / 클레이 애니메이션",
        feature="점토, 종이, 모형 등을 프레임별로 움직이는 연출",
        best_for="재미있는 과학, 어린이 교육, 창의적 영상",
        icon="🧸",
        system_persona="당신은 세계 최고의 AI 쇼츠 영상 디렉터이자 3D 스톱모션 클레이메이션 비주얼 마스터입니다.",
        image_prompt_guide="""- 비주얼 스타일: 아기자기하고 정교한 핸드메이드 3D 스톱모션 클레이메이션 (Cute professional miniature claymation infographic, handcrafted plasticine look).
- 질감 & 디테일: 매크로 접사, 지문 자국, 점토 이음새, 부드러운 무광 질감 (macro photography, visible handcrafted clay fingerprints, hand-molded plasticine textures, soft matte finish, creamy depth of field).
- 스케일: 초미니어처 2~3cm 클레이 피규어와 오브젝트의 극적인 스케일 대비.
- 조명: 부드러운 스튜디오 방향성 림라이트와 깊은 그림자.
- 텍스트 배제: Strictly NO text, NO letters, clean 3D clay visual.""",
        default_concept_style="Cute professional miniature claymation infographic, vertical 9:16, handcrafted plasticine texture, visible fingerprints, stop-motion look, vivid rich studio lighting, macro photography",
        sample_prompt_prefix="Claymation style vertical 9:16 portrait, macro photography. [Scene subject details]. Handcrafted plasticine texture with visible fingerprints, soft studio lighting, creamy bokeh, strictly NO text."
    ),
    VisualStyleItem(
        id="screencast_ui",
        number=9,
        name="스크린캐스트 / UI 애니메이션",
        feature="컴퓨터 화면, 앱 인터페이스, 마우스 움직임을 중심으로 제작",
        best_for="AI 프로그램 소개, 사용법, 자동화",
        icon="💻",
        system_persona="당신은 애플(Apple) / Linear 스타일의 모던 UI/UX 프로덕트 쇼케이스 및 스크린 디자인 아티스트입니다.",
        image_prompt_guide="""- 비주얼 스타일: 세련된 모던 다크모드 소프트웨어 UI 및 가상 디바이스 쇼케이스 (Modern sleek dark-mode glassmorphism UI mockups, clean app dashboard, Apple Keynote aesthetic).
- 인터페이스 디테일: 반투명 글래스모피즘 패널, 은은한 보더 글로우, 깔끔한 카드 레이아웃과 미니멀 대시보드 뷰 (frosted glass panels, subtle border glow, elegant dark dashboard widgets, clean desktop workspace).
- 시점: 3D 아이소메트릭 또는 앵글드 틸트 시점의 디스플레이 샷 (angled perspective view of floating UI cards).
- 텍스트 배제: Strictly NO unreadable blurred fake letters, use clean abstract icons and sleek colored metric bars.""",
        default_concept_style="Modern sleek dark-mode glassmorphism UI showcase, floating holographic app interface, subtle border glow, clean Apple Keynote design aesthetic, vertical 9:16 portrait",
        sample_prompt_prefix="Modern dark-mode glassmorphism UI concept, sleek digital workspace. [Scene subject details]. Angled floating dashboard cards, subtle neon glow, refined minimal tech aesthetic, vertical 9:16, strictly NO fake text."
    ),
    VisualStyleItem(
        id="mixed_media",
        number=10,
        name="믹스드 미디어 (Mixed Media)",
        feature="실사, 사진, 2D, 3D, 자막 등을 조합",
        best_for="다큐멘터리, 과학 해설, 지식 쇼츠",
        icon="🎞️",
        system_persona="당신은 실험적이고 감각적인 현대 다큐멘터리 믹스드 미디어(Mixed-Media Collage) 콜라주 아티스트입니다.",
        image_prompt_guide="""- 비주얼 스타일: 실사 텍스처와 그래픽 요소가 감각적으로 결합된 하이브리드 콜라주 (Artistic mixed-media collage, combining realistic photographic elements with stylized 2D graphic sketches and paper textures).
- 질감 & 레이어: 찢어진 종이 조각 질감, 폴라로이드 사진 프레임, 빈티지 하프톤 도트, 현대적인 3D 요소의 오버레이 (torn paper edges, vintage halftone dot overlays, scrapbook layering, tactile craft mixed with modern graphics).
- 조명 & 분위기: 예술적이고 지적인 다큐멘터리 무드.
- 텍스트 배제: Strictly NO illegible gibberish text, clean visual collage composition.""",
        default_concept_style="Artistic mixed-media collage, realistic photographic elements blended with torn paper craft and halftone graphic layers, tactile documentary aesthetic, vertical 9:16 portrait",
        sample_prompt_prefix="Artistic mixed-media documentary collage, vertical 9:16. [Scene subject details]. Photographic elements combined with torn craft paper textures and subtle graphic overlays, strictly NO text."
    ),
]

VISUAL_STYLES_MAP: dict[str, VisualStyleItem] = {
    s.id: s for s in VISUAL_STYLES
}


def get_visual_style(style_id: str | None) -> VisualStyleItem:
    if not style_id:
        return VISUAL_STYLES_MAP["claymation"]
    return VISUAL_STYLES_MAP.get(style_id, VISUAL_STYLES_MAP["claymation"])

