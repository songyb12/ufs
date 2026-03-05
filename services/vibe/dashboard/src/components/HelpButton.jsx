export default function HelpButton({ section, onNavigate }) {
  return (
    <button
      className="btn btn-help"
      title="사용 가이드 보기"
      onClick={() => onNavigate && onNavigate('guide', section)}
    >
      ?
    </button>
  )
}
