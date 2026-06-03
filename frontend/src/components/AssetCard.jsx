function AssetCard({ asset }) {
  return (
    <div
      style={{
        border: "1px solid #ccc",
        padding: "1rem",
        marginBottom: "1rem",
        borderRadius: "8px",
      }}
    >
      <h3>{asset.name}</h3>

      <p>ID: {asset.id}</p>
    </div>
  );
}

export default AssetCard;