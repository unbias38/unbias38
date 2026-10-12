# Lo-Fi Taiwan Patrol（台灣慢電視漫遊者）

真實台灣即時鏡頭 + Lo-Fi 音樂 + 像素貓的桌面伴讀軟體。

| 檔案 | 內容 |
|---|---|
| [`DESIGN.md`](DESIGN.md) | 六大模組企劃與技術藍圖（GDD、資料管線、視覺、音訊、架構、MVP） |
| [`index.html`](index.html) | MVP 原型：YouTube／HLS 自動判斷、CRT 濾鏡、像素貓行為樹、四軌混音、番茄鐘 |
| [`build_cameras.py`](build_cameras.py) | 資料管線：CSV → `cameras.json` |
| `cameras.json` | 579 台鏡頭（由腳本產生） |
| `data/cameras_source.csv` | 原始資料 |

## 執行 MVP

```bash
python3 -m http.server 8000
# 開 http://localhost:8000/
# 指定串流：http://localhost:8000/?url=<YouTube 或 .m3u8 網址>
```

## 重建鏡頭資料

```bash
python3 build_cameras.py data/cameras_source.csv -o cameras.json          # 保留全部 579 筆
python3 build_cameras.py data/cameras_source.csv -o cameras.json --dedupe # 移除 2 筆重複串流
python3 build_cameras.py data/cameras_source.csv -o cameras.json --resolve-hls-pages  # 嘗試抓出臺北 CCTV 真正的 m3u8
```

- 只用 Python 標準函式庫（3.9 以上）。
- 臺北市 415 筆 `hls.bote.gov.taipei/live/index.html?id=NNN` 是播放器網頁，不是 m3u8，標記為 `player.needs_resolve: true`，MVP 會自動略過。
