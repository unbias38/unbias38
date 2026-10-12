# Lo-Fi Taiwan Patrol：鏡頭資料管線

把 `data/cameras_source.csv`（579 筆台灣即時影像）轉成遊戲用的 `cameras.json`。

```bash
python3 build_cameras.py data/cameras_source.csv -o cameras.json          # 保留全部 579 筆
python3 build_cameras.py data/cameras_source.csv -o cameras.json --dedupe # 移除 2 筆重複串流
python3 build_cameras.py data/cameras_source.csv -o cameras.json --resolve-hls-pages  # 嘗試抓出臺北 CCTV 真正的 m3u8
```

- 只用 Python 標準函式庫（3.9 以上）。
- 分類順序：人工覆寫 → HLS 監控 → 離島 → 海 → 水岸 → 山 → 都市景點；每筆都在 `classification.rule` 記下命中的規則。
- `ambient_sound_profile` 對應到 `ambient_profiles` 裡的混音層設定（給 Web Audio 的 Track 2 使用）。
- 臺北市 415 筆 `hls.bote.gov.taipei/live/index.html?id=NNN` 是播放器網頁，不是 m3u8，所以標記為 `player.needs_resolve: true`。
