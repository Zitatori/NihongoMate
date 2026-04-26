# KoiNihongo

日本語だけで距離が縮まる、LINE風AI会話シミュレーションアプリです。

外国人の日本語学習者が、説明や添削ではなく、会話そのものを通して日本語を使うためのMVPです。

## コンセプト

ユーザーが日本語で「ひな」と会話します。

- 自然に通じる日本語 → 好感度が上がる
- 少し不自然な日本語 → なんとなく伝わる
- 意味が分からない日本語 → ひなが困る

つまり、文法問題ではなく「会話として通じるか」をゲーム化します。

## キャラクター設定

- 名前: ひな
- 年齢: 20歳
- 若い女性キャラクター
- 明るくて少し甘えん坊
- 少し人見知り
- 全年齢向け

## 方針

- 日本語のみ
- 英語なし
- 添削なし
- 文法説明なし
- 会話中心
- 全年齢向け
- 性的表現なし

## 機能

- LINE風チャットUI
- 上部にキャラクター画像
- 表情画像の差し替え
- 好感度スコア
- 関係レベル
- 気分表示
- SQLiteで会話履歴保存
- OpenAI API対応
- APIなし簡易モード

## 実行方法

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windowsの場合:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## OpenAI APIを使う場合

環境変数を設定します。

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

Streamlit Cloudで使う場合は、Secretsに以下を追加します。

```toml
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-4o-mini"
```

## 表情画像の差し替え

以下のファイルを好きな画像に差し替えてください。

```text
assets/hina/normal.png
assets/hina/happy.png
assets/hina/confused.png
assets/hina/sad.png
assets/hina/annoyed.png
```

推奨サイズ:

```text
512 x 512 px
PNG
背景透過でもOK
```

## デプロイ

Streamlit Cloudでそのままデプロイできます。

必要なファイル:

```text
app.py
requirements.txt
assets/hina/*.png
```

`data/koi_nihongo.db` は自動生成されます。

## 今後追加できる機能

- ストーリーイベント
- 日ごとの会話制限
- スタンプ
- 音声入力
- 音声読み上げ
- ログイン
- セーブデータ
- 有料シナリオ
- キャラクター追加
- PWA化
