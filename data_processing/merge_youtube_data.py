import pandas as pd
import glob
from datetime import datetime
import os

# ==========================================
# YouTube 데이터 취합 스크립트
# ==========================================

DATA_DIR = "/Users/leejongmin/code/비모/data/youtube"
OUTPUT_DIR = "/Users/leejongmin/code/비모/data/youtube"

print("\n" + "="*60)
print("📊 YouTube CSV 파일 취합")
print("="*60)

# 모든 CSV 파일 찾기
csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
print(f"\n발견된 CSV 파일: {len(csv_files)}개")

if not csv_files:
    print("❌ CSV 파일이 없습니다.")
    exit(0)

# 파일 목록 출력
for i, file in enumerate(csv_files, 1):
    file_size = os.path.getsize(file) / (1024*1024)  # MB
    print(f"   [{i}] {os.path.basename(file)} ({file_size:.2f} MB)")

# 데이터 읽기 및 통합
print("\n데이터 통합 중...")
all_data = []
total_rows = 0

for file in csv_files:
    try:
        df = pd.read_csv(file)
        all_data.append(df)
        total_rows += len(df)
        print(f"   ✅ {os.path.basename(file)}: {len(df):,}개 행")
    except Exception as e:
        print(f"   ❌ {os.path.basename(file)}: 오류 - {e}")

# 통합 DataFrame 생성
print("\n병합 중...")
merged_df = pd.concat(all_data, ignore_index=True)
print(f"   총 {len(merged_df):,}개 행 (병합 전: {total_rows:,})")

# 중복 제거
print("\n중복 제거 중...")
before_dedup = len(merged_df)

# 완전히 동일한 행만 제거 (모든 컬럼이 같은 경우)
merged_df = merged_df.drop_duplicates(keep='first')
print(f"   제거됨: {before_dedup - len(merged_df):,}개")
print(f"   최종: {len(merged_df):,}개 행")

# 저장
timestamp = datetime.now().strftime('%Y%m%d_%H%M')
output_file = os.path.join(OUTPUT_DIR, f"youtube_merged_{timestamp}.csv")

merged_df.to_csv(output_file, index=False, encoding='utf-8-sig')

print("\n" + "="*60)
print(f"✅ 완료!")
print(f"📁 저장: {output_file}")
print(f"📊 최종 데이터: {len(merged_df):,}개 행")
print("="*60)

# 통계 정보
if 'video_title' in merged_df.columns:
    unique_videos = merged_df['video_title'].nunique()
    print(f"\n🎥 고유 영상: {unique_videos:,}개")

if 'search_keyword' in merged_df.columns:
    print(f"🔑 고유 키워드: {merged_df['search_keyword'].nunique()}개")

if 'comment_text' in merged_df.columns:
    total_comments = merged_df['comment_text'].notna().sum()
    print(f"💬 댓글: {total_comments:,}개")
