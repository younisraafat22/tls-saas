"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  BellRing,
  Check,
  ChevronRight,
  Clock3,
  Database,
  Laptop,
  LockKeyhole,
  MapPin,
  Radio,
  Server,
  ShieldCheck,
} from "lucide-react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { useRef } from "react";
import styles from "./page.module.css";

const branches = [
  { city: "Sheikh Zayed", service: "Legalization", status: "checking" },
  { city: "New Cairo", service: "Visa", status: "quiet" },
  { city: "Alexandria", service: "Visa", status: "quiet" },
  { city: "Hurghada", service: "Legalization", status: "quiet" },
];

const plans = [
  {
    label: "Local monitor",
    price: "300",
    suffix: "EGP / month",
    description: "The checker runs privately on your Windows computer.",
    items: ["One branch", "Email + browser alerts", "60-minute checks"],
  },
  {
    label: "All-in-one",
    price: "500",
    suffix: "EGP / month",
    description: "Switch between legalization and visa monitoring.",
    items: ["Both service types", "Live dashboard", "Desktop application"],
    featured: true,
  },
  {
    label: "Server monitor",
    price: "2,500",
    suffix: "EGP / month",
    description: "Monitoring continues in the cloud without leaving a PC on.",
    items: ["24/7 server runtime", "Encrypted credentials", "Priority support"],
  },
];

function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reducedMotion ? false : { opacity: 0.65, y: 28 }}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function Watchboard() {
  return (
    <div className={styles.watchboard} aria-label="Example monitoring dashboard">
      <div className={styles.boardTopline}>
        <span>EGY / DE APPOINTMENT FEED</span>
        <span className={styles.live}><i /> LIVE</span>
      </div>
      <div className={styles.boardHeader}>
        <span>Branch</span>
        <span>Service</span>
        <span>Status</span>
      </div>
      {branches.map((branch, index) => (
        <motion.div
          className={styles.boardRow}
          key={`${branch.city}-${branch.service}`}
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.25 + index * 0.1 }}
        >
          <strong>{branch.city}</strong>
          <span>{branch.service}</span>
          <span className={branch.status === "checking" ? styles.checking : styles.quiet}>
            {branch.status === "checking" ? "Checking" : "No change"}
          </span>
        </motion.div>
      ))}
      <div className={styles.boardFooter}>
        <span>Last cycle 09:42</span>
        <span>Next cycle 10:42</span>
      </div>
      <div className={styles.alertTicket}>
        <BellRing size={18} />
        <div><b>Slot signal ready</b><span>Email and browser channels armed</span></div>
        <ArrowUpRight size={18} />
      </div>
    </div>
  );
}

export default function HomePage() {
  const heroRef = useRef<HTMLElement>(null);
  const reducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const boardY = useTransform(scrollYProgress, [0, 1], [0, reducedMotion ? 0 : 70]);

  return (
    <main className={styles.site}>
      <div className={styles.notice}>
        <span>MONITORING TOOL</span>
        <p>No automatic booking and no appointment guarantee.</p>
      </div>

      <nav className={styles.nav} aria-label="Primary navigation">
        <Link className={styles.brand} href="/">
          <span className={styles.brandMark}><Radio size={18} /></span>
          <span>TLS / WATCH</span>
        </Link>
        <div className={styles.navLinks}>
          <a href="#process">Process</a>
          <a href="#modes">Modes</a>
          <a href="#engineering">Engineering</a>
          <a href="#pricing">Pricing</a>
        </div>
        <div className={styles.navActions}>
          <Link className={styles.login} href="/login">Log in</Link>
          <Link className={styles.navCta} href="/register">Start monitoring <ArrowUpRight size={15} /></Link>
        </div>
      </nav>

      <section className={styles.hero} ref={heroRef}>
        <div className={styles.heroGrid} aria-hidden="true" />
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}><MapPin size={15} /> Germany appointments · Egypt branches</p>
          <h1>Stop watching<br />the <em>calendar.</em></h1>
          <p className={styles.heroLead}>
            A focused monitoring system for TLS legalization and visa appointment availability—built to check, record, and alert while you get on with your day.
          </p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryButton} href="/register">Begin a free trial <ArrowDownRight size={18} /></Link>
            <a className={styles.textLink} href="#engineering">See how it works <ChevronRight size={17} /></a>
          </div>
          <div className={styles.heroProof}>
            <span><ShieldCheck size={17} /> Monitoring only</span>
            <span><BellRing size={17} /> Multi-channel alerts</span>
            <span><Clock3 size={17} /> Scheduled checks</span>
          </div>
        </div>
        <motion.div className={styles.boardWrap} style={{ y: boardY }}>
          <Watchboard />
        </motion.div>
      </section>

      <section className={styles.metrics} aria-label="Product capabilities">
        <div><strong>7</strong><span>Egypt branches represented</span></div>
        <div><strong>2</strong><span>monitoring modes</span></div>
        <div><strong>3</strong><span>alert channels</span></div>
        <div><strong>24/7</strong><span>server option</span></div>
      </section>

      <section className={styles.statement}>
        <Reveal className={styles.statementInner}>
          <p className={styles.sectionIndex}>01 / THE PROBLEM</p>
          <h2>The appointment should take your attention once—not every five minutes.</h2>
          <p>TLS / WATCH separates detection from action. The system watches availability and tells you when the state changes. You remain in control of booking.</p>
        </Reveal>
      </section>

      <section className={styles.process} id="process">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>02 / PROCESS</p>
          <h2>Four clear handoffs.</h2>
        </div>
        <div className={styles.steps}>
          {[
            ["01", "Choose", "Select legalization or visa and the branch you need."],
            ["02", "Watch", "A scheduled browser worker checks the relevant TLS flow."],
            ["03", "Compare", "Each result is stored and compared with the previous state."],
            ["04", "Alert", "A change triggers email, browser push, and a live dashboard update."],
          ].map(([number, title, copy], index) => (
            <Reveal className={styles.step} key={number}>
              <span>{number}</span>
              <div className={styles.stepLine}><i /></div>
              <h3>{title}</h3>
              <p>{copy}</p>
              {index < 3 && <ArrowDownRight className={styles.stepArrow} size={21} />}
            </Reveal>
          ))}
        </div>
      </section>

      <section className={styles.modes} id="modes">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>03 / TWO MODES</p>
          <h2>Local privacy or cloud continuity.</h2>
          <p>Choose where the browser worker runs. Both modes report into the same account dashboard.</p>
        </div>
        <div className={styles.modeGrid}>
          <Reveal className={styles.modeCard}>
            <div className={styles.modeIcon}><Laptop size={26} /></div>
            <p className={styles.modeTag}>LOCAL / WINDOWS</p>
            <h3>Your machine does the checking.</h3>
            <p>TLS credentials stay encrypted on your computer. Monitoring runs while the application and computer are online.</p>
            <ul>
              <li><Check size={16} /> Local encrypted storage</li>
              <li><Check size={16} /> Desktop and email alerts</li>
              <li><Check size={16} /> Lower-cost plans</li>
            </ul>
            <a href="#pricing">Compare local plans <ArrowUpRight size={16} /></a>
          </Reveal>
          <Reveal className={`${styles.modeCard} ${styles.modeCardDark}`}>
            <div className={styles.modeIcon}><Server size={26} /></div>
            <p className={styles.modeTag}>CLOUD / PREMIUM</p>
            <h3>The service keeps watch.</h3>
            <p>An isolated server worker continues checking around the clock. Credentials are encrypted before database storage.</p>
            <ul>
              <li><Check size={16} /> No computer required</li>
              <li><Check size={16} /> Continuous runtime</li>
              <li><Check size={16} /> Limited monthly capacity</li>
            </ul>
            <a href="#pricing">Review premium <ArrowUpRight size={16} /></a>
          </Reveal>
        </div>
      </section>

      <section className={styles.engineering} id="engineering">
        <Reveal className={styles.engineeringIntro}>
          <p className={styles.sectionIndex}>04 / ENGINEERING</p>
          <h2>A full-stack monitoring pipeline, not a landing-page mock-up.</h2>
          <p>Next.js handles the product interface. FastAPI coordinates account state and background work. Browser workers inspect the external flow, while WebSockets and notification services distribute changes.</p>
        </Reveal>
        <div className={styles.systemDiagram}>
          <div className={styles.systemNode}><span>01</span><strong>Next.js client</strong><small>Account + live dashboard</small></div>
          <i className={styles.connector} />
          <div className={styles.systemNode}><span>02</span><strong>FastAPI core</strong><small>Auth + orchestration</small></div>
          <i className={styles.connector} />
          <div className={styles.systemNode}><span>03</span><strong>Browser worker</strong><small>Scheduled TLS checks</small></div>
          <i className={styles.connector} />
          <div className={styles.systemNode}><span>04</span><strong>Alert fan-out</strong><small>Email + push + socket</small></div>
        </div>
        <div className={styles.techRow}>
          <span><Database size={17} /> PostgreSQL / SQLAlchemy</span>
          <span><LockKeyhole size={17} /> JWT + encrypted credentials</span>
          <span><Radio size={17} /> WebSockets</span>
          <span><Server size={17} /> Docker + Fly.io</span>
        </div>
      </section>

      <section className={styles.pricing} id="pricing">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>05 / PLANS</p>
          <h2>Pay for the runtime you need.</h2>
          <p>All plans are monitoring aids. They do not reserve or book appointments.</p>
        </div>
        <div className={styles.planGrid}>
          {plans.map((plan) => (
            <Reveal className={`${styles.plan} ${plan.featured ? styles.planFeatured : ""}`} key={plan.label}>
              {plan.featured && <span className={styles.planFlag}>MOST FLEXIBLE</span>}
              <p>{plan.label}</p>
              <div className={styles.price}><strong>{plan.price}</strong><span>{plan.suffix}</span></div>
              <p className={styles.planDescription}>{plan.description}</p>
              <ul>{plan.items.map((item) => <li key={item}><Check size={15} /> {item}</li>)}</ul>
              <Link href="/register">Choose plan <ArrowUpRight size={17} /></Link>
            </Reveal>
          ))}
        </div>
      </section>

      <section className={styles.finalCta}>
        <Reveal className={styles.finalCtaInner}>
          <div>
            <p className={styles.sectionIndex}>READY WHEN YOU ARE</p>
            <h2>Let the system keep the watch.</h2>
          </div>
          <Link href="/register">Create an account <ArrowUpRight size={21} /></Link>
        </Reveal>
      </section>

      <footer className={styles.footer}>
        <div className={styles.brand}><span className={styles.brandMark}><Radio size={18} /></span><span>TLS / WATCH</span></div>
        <p>Independent monitoring software. Not affiliated with TLScontact or any embassy.</p>
        <div><Link href="/terms">Terms</Link><Link href="/privacy">Privacy</Link><Link href="/contact">Contact</Link></div>
      </footer>
    </main>
  );
}
