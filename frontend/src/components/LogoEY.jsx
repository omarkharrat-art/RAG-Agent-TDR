// Official-style EY logo: the yellow "beam" wedge above the bold EY wordmark.
// Reproduced as SVG so it stays crisp at any size and can invert for dark/light.
export default function LogoEY({ height = 36, letter = "#ffffff", beam = "#FFE600" }) {
  return (
    <svg
      height={height}
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="EY"
      style={{ display: "block" }}
    >
      {/* Beam: thin point at lower-left, thick blunt end at upper-right. */}
      <polygon points="8,45 95,7 95,29" fill={beam} />
      {/* EY wordmark: bold, tightly spaced. */}
      <text
        x="50"
        y="95"
        textAnchor="middle"
        fontFamily="Arial, Helvetica, sans-serif"
        fontWeight="800"
        fontSize="62"
        letterSpacing="-3"
        fill={letter}
      >
        EY
      </text>
    </svg>
  );
}
