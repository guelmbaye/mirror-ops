import Link from "next/link";

export default function NotFound() {
  return (
    <div className="stage">
      <header className="stage__head">
        <Link href="/" className="wordmark" aria-label="Mirror Ops — home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-mirror-ops.png" alt="Mirror Ops" width={86} height={26} />
        </Link>
      </header>
      <main className="stage__body" style={{ paddingTop: "14vh" }}>
        <p className="eyebrow">Nothing here</p>
        <h1 className="heading">That screen isn&apos;t part of the flow.</h1>
        <p className="body">Every Mirror Ops journey starts from one place.</p>
        <div className="spacer" />
        <div className="stage__foot">
          <Link href="/" className="action">
            Back to the start
          </Link>
        </div>
      </main>
    </div>
  );
}
