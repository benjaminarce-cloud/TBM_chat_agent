import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        color: "white",
        background: "#102a2d",
        fontSize: 10,
        fontWeight: 900,
        letterSpacing: "0.04em",
      }}
    >
      TBM
    </div>,
    size,
  );
}
