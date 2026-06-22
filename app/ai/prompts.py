"""Prompt templates — tách riêng khỏi logic.

Áp dụng kỹ thuật prompt engineering bài 115-122:
  - Bài 115: Composable blocks (PERSONA + FORMAT_RULE tái sử dụng)
  - Bài 117: One-Shot   → build_summarize_prompt (format cố định)
  - Bài 118: Few-Shot   → build_generate_description_prompt (học tone)
  - Bài 119: Structured → build_analysis_prompt (output JSON)
  - Bài 120: CoT        → build_cot_review_prompt (suy luận từng bước)
  - Bài 122: Persona    → BOOK_EXPERT_PERSONA (inject vào mọi prompt)
"""
from __future__ import annotations

# ── Composable blocks (Bài 115) ───────────────────────────────────────────────
# Tái sử dụng qua mọi prompt — thay đổi 1 chỗ → tất cả cùng update

BOOK_EXPERT_PERSONA = """\
Bạn là chuyên gia sách với 20 năm kinh nghiệm trong ngành xuất bản Việt Nam.
Bạn đọc và phân tích hàng nghìn cuốn sách mỗi năm. Bạn trả lời ngắn gọn,
chính xác — không lan man, không thêm lời chào hay câu kết."""
# Bài 122: Persona — định nghĩa "ai đang nói" thay vì chỉ "làm gì"
# Dùng ẩn dụ "knowledgeable friend" để model hiểu tone cần dùng

STRICT_FORMAT_RULE = "Chỉ trả về đúng những gì được yêu cầu. Không thêm lời giải thích."


# ── Summarize (Bài 117: One-Shot) ─────────────────────────────────────────────
# One-Shot = 1 cặp ví dụ → lock format, output nhất quán
# Kết thúc bằng "Output:" → model predict tiếp ngay vào phần trả lời

def build_summarize_prompt(title: str, author: str, description: str | None) -> str:
    """One-Shot: 1 ví dụ đủ để lock format — luôn ra đúng 2-3 câu."""
    return f"""{BOOK_EXPERT_PERSONA}
{STRICT_FORMAT_RULE}

Tóm tắt sách trong 2-3 câu tiếng Việt. Chỉ trả về phần tóm tắt.

Ví dụ:
Input: "Atomic Habits" - James Clear - Sách về xây dựng thói quen nhỏ mỗi ngày để tạo kết quả lớn.
Output: Atomic Habits chỉ ra rằng cải thiện 1% mỗi ngày tạo ra kết quả vượt bậc theo thời gian. James Clear cung cấp hệ thống thực tế: gắn thói quen mới vào thói quen cũ và tập trung vào danh tính thay vì kết quả. Cuốn sách thay đổi hoàn toàn cách nhìn về việc xây dựng thói quen bền vững.

Input: "{title}" - {author} - {description or "Không có mô tả"}
Output:"""


# ── Generate Description (Bài 118: Few-Shot) ─────────────────────────────────
# Few-Shot = 3 ví dụ → model học TONE và STYLE, không chỉ format
# Đa dạng ví dụ (kỹ thuật, văn học, thiếu nhi) → generalize tốt hơn

def build_generate_description_prompt(title: str, author: str, category: str) -> str:
    """Few-Shot: 3 ví dụ đa dạng → model học tone hấp dẫn, không spoiler."""
    return f"""{BOOK_EXPERT_PERSONA}
Viết mô tả 3-4 câu, hấp dẫn, tiếng Việt, không spoiler.

---
"Clean Code" - Robert C. Martin - Lập trình
Mô tả: Clean Code là kim chỉ nam cho lập trình viên muốn viết code dễ đọc và dễ bảo trì. Robert Martin chia sẻ nguyên tắc, pattern và thực hành tốt nhất qua các ví dụ refactor thực tế. Cuốn sách dạy không chỉ cách viết code chạy được, mà còn viết code người khác có thể hiểu. Bắt buộc đọc cho mọi lập trình viên nghiêm túc về nghề.

---
"Dế Mèn Phiêu Lưu Ký" - Tô Hoài - Văn học thiếu nhi
Mô tả: Dế Mèn Phiêu Lưu Ký dẫn độc giả vào thế giới côn trùng đầy màu sắc qua đôi mắt chú dế mèn dũng cảm. Tô Hoài khắc họa những cuộc phiêu lưu kỳ thú với văn phong trong sáng, giàu hình ảnh phù hợp mọi lứa tuổi. Bên cạnh hành trình phiêu lưu, cuốn sách gửi gắm bài học đẹp về tình bạn và lòng dũng cảm. Kiệt tác của văn học thiếu nhi Việt Nam đã đồng hành nhiều thế hệ.

---
"Sapiens" - Yuval Noah Harari - Lịch sử
Mô tả: Sapiens kể lại toàn bộ lịch sử loài người từ 70.000 năm trước đến ngày nay trong một cuốn sách đầy tính giải trí. Harari lý giải tại sao Homo sapiens thống trị Trái Đất và cách các "huyền thoại chung" như tiền tệ, tôn giáo, quốc gia đã gắn kết hàng triệu người lạ. Đây là cuốn sách thay đổi cách bạn nhìn thế giới và bản thân mình. Đọc xong bạn sẽ không thể thôi suy nghĩ về câu hỏi: con người là gì?

---
"{title}" - {author} - {category}
Mô tả:"""


# ── Book Analysis (Bài 119: Structured Output + Bài 120: CoT) ─────────────────
# Structured: buộc output ra JSON parsable
# CoT: "Phân tích từng khía cạnh" → model suy luận có bằng chứng
# Ví dụ inline (one-shot) để lock JSON schema

def build_analysis_prompt(title: str, author: str, description: str | None) -> str:
    """One-Shot + Structured Output: trả về JSON phân tích sách.

    temperature nên để thấp (0.1-0.2) khi gọi hàm này — cần deterministic.
    """
    return f"""{BOOK_EXPERT_PERSONA}
Phân tích sách và trả về JSON. CHỈ trả về JSON hợp lệ, không có text khác.

Ví dụ:
Input: "Atomic Habits" - James Clear - Hướng dẫn xây dựng thói quen nhỏ mỗi ngày
Output: {{"genre": "self-help", "difficulty": "beginner", "tags": ["thói quen", "năng suất", "tâm lý học"], "mood": "motivating", "age_group": "adult", "rating_prediction": 4.3}}

Input: "{title}" - {author} - {description or "Không có mô tả"}
Output:"""


# ── CoT Review (Bài 120: Chain-of-Thought) ────────────────────────────────────
# Dùng cho task cần suy luận đa chiều — phán đoán độ tuổi phù hợp
# Kết thúc bằng "Bước 1 -" → model tự tiếp tục từng bước

def build_cot_age_check_prompt(title: str, description: str | None) -> str:
    """CoT: suy luận từng bước trước khi kết luận độ tuổi phù hợp.

    Dùng khi cần accuracy cao — tốn thêm token nhưng chính xác hơn zero-shot.
    """
    return f"""{BOOK_EXPERT_PERSONA}
Đánh giá độ tuổi phù hợp cho sách theo từng bước. Cuối cùng trả về JSON:
{{"suitable_age": "children|teen|adult|all", "reason": "...", "content_warnings": []}}

Sách: "{title}"
Mô tả: {description or "Không có mô tả"}

Bước 1 - Thể loại và nội dung chính:"""
# Trick: kết thúc giữa chừng → model viết tiếp "Bước 1 - Fiction, ..."
# rồi tự suy ra Bước 2, 3... và kết luận bằng JSON


# ── Embedding text (không cần LLM) ────────────────────────────────────────────

def build_embedding_text(title: str, description: str | None) -> str:
    """Tạo text input cho embedding — càng nhiều context càng chính xác.

    Giới hạn 8000 ký tự để không vượt token limit của text-embedding-3-small.
    """
    text = title
    if description:
        text += f". {description}"
    return text[:8000]
