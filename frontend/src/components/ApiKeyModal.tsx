import { useEffect, useState } from "react";

type ApiKeyModalProps = {
  isOpen: boolean;
  initialValue: string;
  onSave: (value: string) => void;
  onClose: () => void;
};

export function ApiKeyModal({
  isOpen,
  initialValue,
  onSave,
  onClose,
}: ApiKeyModalProps) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue, isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <p className="section-eyebrow">API 管理</p>
        <h2>Gemini API キーを入力</h2>
        <p className="modal-warning">
          この Pages デモでは API キーをブラウザから直接利用します。キーは秘匿できず、
          localStorage に保存されます。共用端末では保存しないでください。デモ用または利用制限付きキーを推奨します。
        </p>
        <label className="field">
          <span>Gemini API キー</span>
          <input
            type="password"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="AIza..."
          />
        </label>
        <div className="modal-actions">
          <button
            type="button"
            className="primary"
            onClick={() => onSave(value.trim())}
          >
            保存して続行
          </button>
          <button type="button" className="ghost" onClick={onClose}>
            データ確認のみで続行
          </button>
        </div>
      </div>
    </div>
  );
}
