export default function Preview() {
  return (
    <div style={{
      width: "100%",
      border: "1px solid #e5e7eb",
      borderRadius: "8px",
      overflow: "hidden",
      backgroundColor: "white",
    }}>
      <div style={{
        padding: "8px 12px",
        borderBottom: "1px solid #e5e7eb",
        backgroundColor: "#f9fafb",
        fontSize: "12px",
        color: "#6b7280",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span>Live preview - http://localhost:3000</span>
        <button
          onClick={() => {
            const iframe = document.getElementById("lingua-preview");
            if (iframe) iframe.src = iframe.src;
          }}
          style={{
            padding: "2px 8px",
            fontSize: "11px",
            border: "1px solid #d1d5db",
            borderRadius: "4px",
            backgroundColor: "white",
            cursor: "pointer",
          }}
        >
          Refresh
        </button>
      </div>
      <iframe
        id="lingua-preview"
        src="http://localhost:3000"
        style={{
          width: "100%",
          height: "600px",
          border: "none",
          display: "block",
        }}
        title="Live preview"
      />
    </div>
  );
}
