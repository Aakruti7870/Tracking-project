import fs from 'node:fs';

const patchFile = (path, transforms) => {
  let source = fs.readFileSync(path, 'utf8');
  const before = source;
  for (const [from, to] of transforms) {
    if (source.includes(to)) continue;
    if (!source.includes(from)) {
      throw new Error(`Expected hero source fragment not found in ${path}: ${from.slice(0, 90)}`);
    }
    source = source.replace(from, to);
  }
  if (source !== before) fs.writeFileSync(path, source);
};

patchFile('frontend/app/login.tsx', [
  [
    'const HERO = require("../assets/images/industrial-rmc-hero.jpg");',
    'const HERO_LIGHT = require("../assets/images/login-hero-light.jpg");\nconst HERO_DARK = require("../assets/images/login-hero-dark.jpg");'
  ],
  [
    '  const { colors } = useTheme();\n  const router = useRouter();',
    '  const { colors } = useTheme();\n  const heroSource = colors.isDark ? HERO_DARK : HERO_LIGHT;\n  const router = useRouter();'
  ],
  [
    '      <StatusBar style="light" />',
    '      <StatusBar style={colors.isDark ? "light" : "dark"} />'
  ],
  [
    '        <View style={styles.hero}> \n          <Image source={HERO} style={StyleSheet.absoluteFill} contentFit="cover" contentPosition="center" transition={180} />\n          <LinearGradient pointerEvents="none" colors={["rgba(0,0,0,0.05)", "rgba(0,0,0,0)", colors.surface]} locations={[0, 0.76, 1]} style={StyleSheet.absoluteFill} />',
    '        <View style={[styles.hero, { backgroundColor: colors.isDark ? "#080A0C" : "#F5F6F4" }]}> \n          <Image source={heroSource} style={StyleSheet.absoluteFill} contentFit="contain" contentPosition="center" transition={180} />\n          <LinearGradient pointerEvents="none" colors={colors.isDark ? ["rgba(0,0,0,0.02)", "rgba(0,0,0,0)", colors.surface] : ["rgba(255,255,255,0)", "rgba(255,255,255,0)", colors.surface]} locations={[0, 0.76, 1]} style={StyleSheet.absoluteFill} />'
  ],
  [
    '  hero: { height: 300, justifyContent: "flex-start", overflow: "hidden", backgroundColor: "#080A0C" },',
    '  hero: { height: 300, justifyContent: "center", overflow: "hidden" },'
  ]
]);

patchFile('frontend/app/customer/index.tsx', [
  [
    'const HERO = require("../../assets/images/industrial-rmc-hero.jpg");',
    'const HERO_LIGHT = require("../../assets/images/home-hero-light.jpg");\nconst HERO_DARK = require("../../assets/images/home-hero-dark.jpg");'
  ],
  [
    '  const { colors } = useTheme();\n  const { user } = useAuth();',
    '  const { colors } = useTheme();\n  const heroSource = colors.isDark ? HERO_DARK : HERO_LIGHT;\n  const { user } = useAuth();'
  ],
  [
    '              <View style={[styles.hero, { backgroundColor: "#0A0C0E" }]}> \n                <Image source={HERO} style={StyleSheet.absoluteFill} contentFit="cover" contentPosition="right center" transition={180} />\n                <LinearGradient colors={["rgba(5,7,9,0.98)", "rgba(5,7,9,0.86)", "rgba(5,7,9,0.35)", "rgba(5,7,9,0.08)"]} locations={[0, 0.38, 0.7, 1]} style={StyleSheet.absoluteFill} />',
    '              <View style={[styles.hero, { backgroundColor: colors.isDark ? "#080A0C" : "#F5F6F4" }]}> \n                <Image source={heroSource} style={StyleSheet.absoluteFill} contentFit="contain" contentPosition="right center" transition={180} />\n                <LinearGradient colors={colors.isDark ? ["rgba(5,7,9,0.96)", "rgba(5,7,9,0.78)", "rgba(5,7,9,0.18)", "rgba(5,7,9,0)"] : ["rgba(247,248,246,0.98)", "rgba(247,248,246,0.82)", "rgba(247,248,246,0.16)", "rgba(247,248,246,0)"]} locations={[0, 0.38, 0.7, 1]} style={StyleSheet.absoluteFill} />'
  ],
  [
    '                  <AppText style={[styles.heroLine, { color: "#FFFFFF" }]}>Track.</AppText>\n                  <AppText style={[styles.heroLine, { color: "#FFFFFF" }]}>Order.</AppText>',
    '                  <AppText style={[styles.heroLine, { color: colors.isDark ? "#FFFFFF" : colors.onSurface }]}>Track.</AppText>\n                  <AppText style={[styles.heroLine, { color: colors.isDark ? "#FFFFFF" : colors.onSurface }]}>Order.</AppText>'
  ],
  [
    '                  <AppText style={[styles.heroSub, { color: "rgba(255,255,255,0.76)" }]}>Your concrete. Our commitment.{"\\n"}All in one place.</AppText>',
    '                  <AppText style={[styles.heroSub, { color: colors.isDark ? "rgba(255,255,255,0.76)" : colors.onSurfaceSecondary }]}>Your concrete. Our commitment.{"\\n"}All in one place.</AppText>'
  ],
  [
    '  hero: { minHeight: 430, borderRadius: 32, overflow: "hidden", position: "relative", backgroundColor: "#0A0C0E" },',
    '  hero: { minHeight: 430, borderRadius: 32, overflow: "hidden", position: "relative", justifyContent: "center" },'
  ]
]);

console.log('Responsive theme hero patch applied.');
