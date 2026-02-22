Nhìn lại `models.py` đã viết, có 3 models tương ứng 3 bảng trong DB:

---

## Listing – Bảng trung tâm

Đây là bảng lưu **raw data từ crawler**. Mọi thứ crawl được từ ImmobilienScout24 hay Kleinanzeigen đều vào đây.

```python
class Listing(Base):
    __tablename__ = "listings"
```

Có thể chia nội dung thành 6 nhóm:

**Identity** – biết listing này đến từ đâu, tránh crawl trùng:
```python
source     = "immoscout" | "kleinanzeigen"
source_id  = ID gốc trên trang đó
source_url = link gốc để user click vào xem
```

**Financials** – số tiền liên quan:
```python
mietpreis   # tiền thuê hàng tháng
ablöse      # phí sang nhượng từ người thuê cũ
kaution     # tiền đặt cọc
nebenkosten # điện nước rác
```

**Physical** – đặc điểm vật lý mặt bằng:
```python
flaeche_m2  # diện tích
etage       # tầng – rất quan trọng, nail/nhà hàng cần tầng trệt
kueche      # có bếp không
lueftung    # thông gió – nail cần vì hóa chất
wasseranschluss  # đường nước – nail cần nhiều
starkstrom  # điện 3 pha – bếp công nghiệp cần
parkplaetze # bãi đỗ xe
```

**Location** – vị trí địa lý:
```python
stadt / bundesland / plz / adresse  # địa chỉ text
lat / lng   # tọa độ sau khi geocode – dùng cho map và spatial queries
```

**AI fields** – phục vụ semantic search:
```python
embedding   # vector 1536 dims của beschreibung
            # dùng để tìm listing tương tự bằng ngôn ngữ tự nhiên
```

**Meta** – quản lý vòng đời listing:
```python
status      # active | inactive | deleted
raw_data    # JSONB – toàn bộ scraped payload
            # quan trọng: nếu parse logic sai có thể re-parse
            # mà không cần crawl lại
first_seen  # lần đầu thấy listing này
last_seen   # lần cuối crawler thấy listing còn tồn tại
            # nếu last_seen cũ hơn 30 ngày → đánh dấu inactive
```

---

## LocationIntel – Bảng cache địa điểm

Đây là bảng lưu **thông tin về khu vực xung quanh**, không phải về mặt bằng cụ thể. Thiết kế tách ra vì một PLZ có thể có hàng trăm listings – không cần gọi Overpass API 100 lần cho cùng một khu vực.

```python
class LocationIntel(Base):
    __tablename__ = "location_intel"
```

**Primary key logic:**
```python
plz       # postal code – ví dụ "60311" (Frankfurt Innenstadt)
radius_m  # 500 | 1000 | 2000 – tùy mức độ phân tích
```

Nghĩa là `plz="60311"` + `radius_m=500` là một record. Nếu cần radius khác thì tạo record khác.

**Demographics** – dữ liệu dân số từ Destatis:
```python
einwohner         # tổng dân số trong radius
einwohner_dichte  # mật độ dân số per km²
kaufkraft_index   # sức mua tiêu dùng, 100 = trung bình DE
                  # Frankfurt ~115, vùng nông thôn ~85
altersstruktur    # JSONB: {"0-18": 18, "18-65": 62, "65+": 20}
                  # quan trọng cho nail – khách chủ yếu 25-50
```

**Competitors** – đối thủ cạnh tranh:
```python
competitors      # JSONB: [{name, category, distance_m, rating}]
competitor_count # tổng số đối thủ trong radius
```

Lưu dạng JSONB thay vì bảng riêng vì không cần query từng competitor, chỉ cần đếm và aggregate.

**Economics** – kinh tế khu vực:
```python
mietspiegel      # giá thuê trung bình €/m² trong khu vực
                 # dùng để đánh giá listing có overpriced không
leerstandsquote  # tỷ lệ mặt bằng trống – cao nghĩa là khu vực đang xuống
```

**Previous tenant** – người thuê cũ:
```python
vormieter_typ   # "nail" | "restaurant" | "unknown"
vormieter_data  # JSONB: thông tin chi tiết nếu có
```

Rất quan trọng khi đánh giá Ablöse – nếu người thuê cũ cũng là nail studio thì cơ sở hạ tầng (nước, thông gió) thường đã có sẵn.

---

## ListingScore – Bảng kết quả chấm điểm

Lưu **kết quả của scoring engine** cho từng listing theo từng ngành. Tách ra khỏi `Listing` vì:
- Score có thể recalculate khi weights thay đổi mà không đụng vào raw data
- Một listing có nhiều scores – một cho nail, một cho restaurant

```python
class ListingScore(Base):
    __tablename__ = "listing_scores"
```

**Composite primary key:**
```python
listing_id + branche  # "nail_studio" | "restaurant" | "imbiss"
```

Nghĩa là cùng một listing có thể có 2 rows – một đánh giá cho nail, một cho nhà hàng.

**Score breakdown** – không chỉ lưu tổng điểm, lưu cả breakdown để giải thích:
```python
score_gesamt    # tổng điểm 0–10
score_location  # điểm vị trí – gần trung tâm, foot traffic
score_financial # điểm tài chính – giá/m², ablöse có hợp lý không
score_physical  # điểm cơ sở vật chất – có nước, bếp, thông gió
score_market    # điểm thị trường – ít đối thủ, kaufkraft cao
```

User nhìn vào biết ngay tại sao score cao hay thấp.

**Revenue estimate:**
```python
revenue_min        # ước tính doanh thu tối thiểu €/năm
revenue_max        # ước tính doanh thu tối đa €/năm
revenue_confidence # 0.0–1.0 – mức độ tin cậy của ước tính
                   # thấp nếu thiếu data demographics
```

**Explanation** – dùng để AI giải thích cho user:
```python
explanation  # JSONB: {
             #   "strengths": ["tầng trệt", "ít đối thủ"],
             #   "weaknesses": ["ablöse cao", "không có thông gió"],
             #   "recommendation": "Phù hợp nếu ablöse dưới 10k€"
             # }
```

---

## Mối quan hệ giữa 3 models

```
Listing (1) ──────────────── (n) ListingScore
    │                              │
    │ lat/lng/plz                  │ branche
    │                              │
    ▼                              ▼
LocationIntel              nail_scorer.py
(lookup by plz)            restaurant_scorer.py

Listing không có FK đến LocationIntel
vì lookup theo plz dynamically,
không phải hard link
```

**Listing** không có foreign key trực tiếp đến `LocationIntel`. Thay vào đó khi scoring, service tự lookup `LocationIntel` theo `plz` của listing. Thiết kế này cho phép một `LocationIntel` record phục vụ nhiều listings trong cùng khu vực mà không cần duplicate data.