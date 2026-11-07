import static com.local.cinefusetv.MainActivity.isSite;

/** Run by build.sh: main-frame navigation stays on cinefuse.<TLD>, everything else is blocked. */
public class SiteCheck {
    public static void main(String[] a) {
        String[] ok = {"cinefuse.cc", "cinefuse.icu", "cinefuse.mom", "cinefuse.sbs", "CINEFUSE.SBS", "www.cinefuse.sbs"};
        String[] blocked = {null, "", "cinefuse", "notcinefuse.sbs", "cinefuse.sbs.evil.com", "cinefuse.co.uk", "ads.example.com", "vidmoly.to"};
        for (String h : ok) if (!isSite(h)) throw new AssertionError("should be allowed: " + h);
        for (String h : blocked) if (isSite(h)) throw new AssertionError("should be blocked: " + h);
        System.out.println("SiteCheck OK (" + (ok.length + blocked.length) + " hosts)");
    }
}
