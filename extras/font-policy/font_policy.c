// Donut process-local CJK + emoji font policy. Inactive unless DONUT_FONT_POLICY=latin-only.
// No system configuration or font files are changed. Public CoreText entrypoints only.
#include <CoreText/CoreText.h>
#include <CoreGraphics/CoreGraphics.h>
#include <CoreFoundation/CoreFoundation.h>
#include <dispatch/dispatch.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>
#include <stdatomic.h>
#include <dlfcn.h>
#include <libproc.h>

#define INTERPOSE(replacement, original) \
 __attribute__((used)) static struct { const void *replacement; const void *original; } \
 ip_##original __attribute__((section("__DATA,__interpose"))) = { (const void *)&replacement, (const void *)&original }

static bool enabled(void) { const char *p=getenv("DONUT_FONT_POLICY"); return p && strcmp(p,"latin-only")==0; }
// Test-only observation, emitted on the first real glyph/cmap call rather than
// at dylib construction. sandbox_check queries policy only; it never opens the
// probe file. A raw -2 means the private diagnostic symbol was unavailable.
static void trace_call(bool glyph) {
 const char *trace=getenv("DONUT_FONT_POLICY_TRACE");if(!trace||strcmp(trace,"1"))return;
 static atomic_bool glyph_seen=false,cmap_seen=false;atomic_bool *seen=glyph?&glyph_seen:&cmap_seen;
 bool expected=false;if(!atomic_compare_exchange_strong(seen,&expected,true))return;
 char process[128]={0};proc_name(getpid(),process,sizeof process);
 for(size_t i=0;process[i];i++)if((unsigned char)process[i]<32||process[i]=='"'||process[i]=='\\')process[i]='_';
 typedef int (*SandboxCheck)(pid_t,const char*,int,...);SandboxCheck check=(SandboxCheck)dlsym(RTLD_DEFAULT,"sandbox_check");
 if(!check){void *handle=dlopen("/usr/lib/libsandbox.1.dylib",RTLD_LAZY|RTLD_LOCAL);if(handle)check=(SandboxCheck)dlsym(handle,"sandbox_check");}
 int result=check?check(getpid(),"file-read-data",1,"/private/etc/sudoers"):-2;
 fprintf(stderr,"[donut-font-policy] event=%s pid=%d process=\"%s\" mode=latin-only-noemoji sandbox_check_file_read_data=%d probe=system-policy\n",glyph?"glyph":"cmap",getpid(),process,result);
}
static const uint32_t ranges[][2] = {
 {0x2e80,0x2fff},{0x3000,0x303f},{0x3040,0x30ff},{0x3100,0x312f},
 {0x3130,0x318f},{0x31a0,0x31bf},{0x31c0,0x31ef},{0x31f0,0x31ff},
 {0x3200,0x33ff},{0x3400,0x4dbf},{0x4e00,0x9fff},{0xa960,0xa97f},
 {0xac00,0xd7ff},{0xf900,0xfaff},{0xfe30,0xfe4f},{0xff00,0xffef},
 {0x16fe0,0x16fff},{0x17000,0x18dff},{0x1aff0,0x1b2ff},
 {0x20000,0x2ffff},{0x30000,0x323af}
};
// Emoji pictographs (Unicode planes 1 and 2 presentation blocks). Apple Color
// Emoji is additionally excluded by name and by kCTFontTraitColorGlyphs, so no
// color emoji font is ever selected and these code points stay unmapped.
// Text-default symbols outside these planes (©, ®, ™, arrows) remain text.
static const uint32_t emoji_ranges[][2] = {
 {0x1f000,0x1faff}
};
static bool blocked(uint32_t cp) {
 for(size_t i=0;i<sizeof(ranges)/sizeof(*ranges);i++) if(cp>=ranges[i][0]&&cp<=ranges[i][1])return true;
 for(size_t i=0;i<sizeof(emoji_ranges)/sizeof(*emoji_ranges);i++) if(cp>=emoji_ranges[i][0]&&cp<=emoji_ranges[i][1])return true;
 return false;
}
static CFCharacterSetRef allowed_set(void) {
 static CFCharacterSetRef set; static dispatch_once_t once;
 dispatch_once(&once, ^{ CFMutableCharacterSetRef b=CFCharacterSetCreateMutable(NULL);
  for(size_t i=0;i<sizeof(ranges)/sizeof(*ranges);i++) CFCharacterSetAddCharactersInRange(b,CFRangeMake(ranges[i][0],ranges[i][1]-ranges[i][0]+1));
  for(size_t i=0;i<sizeof(emoji_ranges)/sizeof(*emoji_ranges);i++) CFCharacterSetAddCharactersInRange(b,CFRangeMake(emoji_ranges[i][0],emoji_ranges[i][1]-emoji_ranges[i][0]+1));
  CFCharacterSetInvert(b);set=b; });return set;
}
static CFCharacterSetRef non_han_set(void) {
 static CFCharacterSetRef set; static dispatch_once_t once;
 dispatch_once(&once, ^{CFMutableCharacterSetRef b=CFCharacterSetCreateMutable(NULL);
 const uint32_t han[][2]={{0x3400,0x4dbf},{0x4e00,0x9fff},{0xf900,0xfaff},{0x20000,0x2ffff},{0x30000,0x323af}};
 for(size_t i=0;i<sizeof(han)/sizeof(*han);i++)CFCharacterSetAddCharactersInRange(b,CFRangeMake(han[i][0],han[i][1]-han[i][0]+1));
 CFCharacterSetInvert(b);set=b;});return set;
}
static bool name_blocked(CFStringRef name) {
 if(!name)return false;
 const CFStringRef names[]={CFSTR("PingFang"),CFSTR("Hiragino"),CFSTR("Heiti"),CFSTR("Songti"),CFSTR("Kaiti"),CFSTR("STSong"),CFSTR("STFangsong"),CFSTR("SimSun"),CFSTR("SimHei"),CFSTR("Noto Sans CJK"),CFSTR("Noto Serif CJK"),CFSTR("Source Han"),CFSTR("YuGothic"),CFSTR("YuMincho"),CFSTR("Apple SD Gothic"),CFSTR("AppleMyungjo"),CFSTR("LiSong"),CFSTR("LiHei"),CFSTR("Baoli"),CFSTR("HanziPen"),CFSTR("Wawati"),CFSTR("Weibei"),CFSTR("Xingkai"),CFSTR("Yuppy"),CFSTR("LingWai"),
  CFSTR("Microsoft YaHei"),CFSTR("MicrosoftYaHei"),CFSTR("Microsoft JhengHei"),CFSTR("MicrosoftJhengHei"),CFSTR("NSimSun"),CFSTR("MingLiU"),CFSTR("PMingLiU"),CFSTR("DengXian"),CFSTR("FangSong"),CFSTR("Yu Gothic"),CFSTR("Meiryo"),CFSTR("Malgun Gothic"),CFSTR("MS Gothic"),CFSTR("MS Mincho"),CFSTR("Color Emoji"),CFSTR("AppleColorEmoji"),CFSTR("NotoColorEmoji"),CFSTR("Twemoji"),CFSTR("EmojiOne"),CFSTR("Segoe UI Emoji")};
 for(size_t i=0;i<sizeof(names)/sizeof(*names);i++)if(CFStringFind(name,names[i],kCFCompareCaseInsensitive).location!=kCFNotFound)return true;
 return false;
}
// Color fonts (sbix/COLR/CBDT/CBLC/SVG) never serve the window, even when a
// third-party font omits the standard color trait.
static bool color_table_font(CTFontRef font) {
 if(!font)return false;
 static const CTFontTableTag tags[]={0x73626978,0x434f4c52,0x43424454,0x43424c43,0x53564720};
 for(size_t i=0;i<sizeof(tags)/sizeof(*tags);i++){CFDataRef d=CTFontCopyTable(font,tags[i],0);if(d){CFRelease(d);return true;}}
 return false;
}
static bool font_blocked(CTFontRef font) {
 if(!font)return false;
 if(CTFontGetSymbolicTraits(font)&kCTFontTraitColorGlyphs)return true;
 CFStringRef n=CTFontCopyPostScriptName(font); bool bad=name_blocked(n);if(n)CFRelease(n);if(bad)return true;
 CFCharacterSetRef cs=CTFontCopyCharacterSet(font);
 if(cs){bad=!CFCharacterSetIsSupersetOfSet(non_han_set(),cs);CFRelease(cs);}return bad;
}
static bool normalized(CFStringRef name){
 if(!name)return false;
 const CFStringRef names[]={CFSTR("Menlo"),CFSTR("Times"),CFSTR("Courier"),CFSTR("Segoe UI"),CFSTR("Calibri"),CFSTR("Cambria"),CFSTR("Consolas"),CFSTR("Tahoma"),CFSTR("Trebuchet MS"),CFSTR("Arial Black"),CFSTR("Impact"),CFSTR("Lucida Console"),CFSTR("MS Sans Serif"),CFSTR("Candara"),CFSTR("Corbel"),CFSTR("Constantia"),CFSTR("Franklin Gothic"),CFSTR("Gabriola"),CFSTR("Palatino Linotype"),CFSTR("Book Antiqua"),CFSTR("Century Gothic"),CFSTR("Comic Sans MS")};
 for(size_t i=0;i<sizeof(names)/sizeof(*names);i++)if(CFStringFind(name,names[i],kCFCompareCaseInsensitive).location!=kCFNotFound)return true;
 return false;
}
// Blocked families and the monospace/serif generic baselines all resolve to
// Helvetica, so width probes compare Helvetica with Helvetica.
static CTFontRef safe_font(CTFontRef font) {
 if(!font || !enabled())return font;
 CFStringRef n=CTFontCopyPostScriptName(font);
 bool norm = n && normalized(n);
 if(n)CFRelease(n);
 if(!norm && !font_blocked(font))return font;
 CGFloat s=CTFontGetSize(font); CGAffineTransform matrix=CTFontGetMatrix(font);CFRelease(font);
 return CTFontCreateWithName(CFSTR("Helvetica"),s,&matrix);
}
static bool descriptor_blocked(CTFontDescriptorRef d) {
 CFStringRef n=CTFontDescriptorCopyAttribute(d,kCTFontNameAttribute);
 bool bad=n && CFGetTypeID(n)==CFStringGetTypeID() && name_blocked(n);if(n)CFRelease(n);
 if(bad)return true;CTFontRef f=CTFontCreateWithFontDescriptor(d,12,NULL);bad=font_blocked(f);if(f)CFRelease(f);return bad;
}
static CFArrayRef filter_descriptors(CFArrayRef a) {
 if(!enabled()||!a)return a;CFMutableArrayRef out=CFArrayCreateMutable(NULL,0,&kCFTypeArrayCallBacks);
 for(CFIndex i=0;i<CFArrayGetCount(a);i++){CTFontDescriptorRef d=(CTFontDescriptorRef)CFArrayGetValueAtIndex(a,i);if(!descriptor_blocked(d))CFArrayAppendValue(out,d);}CFRelease(a);return out;
}
static CFArrayRef policy_families(void) {
 CFArrayRef a=CTFontManagerCopyAvailableFontFamilyNames();if(!enabled()||!a)return a;
 CFMutableArrayRef out=CFArrayCreateMutable(NULL,0,&kCFTypeArrayCallBacks);
 for(CFIndex i=0;i<CFArrayGetCount(a);i++){CFStringRef name=(CFStringRef)CFArrayGetValueAtIndex(a,i);CTFontRef f=CTFontCreateWithName(name,12,NULL);bool bad=name_blocked(name)||font_blocked(f)||color_table_font(f);if(f)CFRelease(f);if(!bad)CFArrayAppendValue(out,name);}CFRelease(a);return out;
}
static CFArrayRef policy_postscripts(void) {
 CFArrayRef a=CTFontManagerCopyAvailablePostScriptNames();if(!enabled()||!a)return a;CFMutableArrayRef out=CFArrayCreateMutable(NULL,0,&kCFTypeArrayCallBacks);
 for(CFIndex i=0;i<CFArrayGetCount(a);i++){CFStringRef name=(CFStringRef)CFArrayGetValueAtIndex(a,i);CTFontRef f=CTFontCreateWithName(name,12,NULL);bool bad=name_blocked(name)||font_blocked(f)||color_table_font(f);if(f)CFRelease(f);if(!bad)CFArrayAppendValue(out,name);}CFRelease(a);return out;
}
static CFArrayRef policy_collection(CTFontCollectionRef c){return filter_descriptors(CTFontCollectionCreateMatchingFontDescriptors(c));}
static CFArrayRef policy_collection_options(CTFontCollectionRef c,CFDictionaryRef o){return filter_descriptors(CTFontCollectionCreateMatchingFontDescriptorsWithOptions(c,o));}
static CFArrayRef policy_collection_family(CTFontCollectionRef c,CFStringRef n,CFDictionaryRef o){return filter_descriptors(CTFontCollectionCreateMatchingFontDescriptorsForFamily(c,n,o));}
static CFArrayRef policy_collection_sorted(CTFontCollectionRef c,CTFontCollectionSortDescriptorsCallback s,void *r){return filter_descriptors(CTFontCollectionCreateMatchingFontDescriptorsSortedWithCallback(c,s,r));}
static CFArrayRef policy_descriptors(CTFontDescriptorRef d,CFSetRef s){return filter_descriptors(CTFontDescriptorCreateMatchingFontDescriptors(d,s));}
static CTFontDescriptorRef policy_descriptor(CTFontDescriptorRef d,CFSetRef s){CTFontDescriptorRef r=CTFontDescriptorCreateMatchingFontDescriptor(d,s);if(enabled()&&r&&descriptor_blocked(r)){CFRelease(r);return NULL;}return r;}
static CTFontRef policy_name(CFStringRef n,CGFloat s,const CGAffineTransform *m){return safe_font(CTFontCreateWithName(n,s,m));}
static CTFontRef policy_name_options(CFStringRef n,CGFloat s,const CGAffineTransform *m,CTFontOptions o){return safe_font(CTFontCreateWithNameAndOptions(n,s,m,o));}
static CTFontRef policy_font_descriptor(CTFontDescriptorRef d,CGFloat s,const CGAffineTransform *m){return safe_font(CTFontCreateWithFontDescriptor(d,s,m));}
static CTFontRef policy_font_descriptor_options(CTFontDescriptorRef d,CGFloat s,const CGAffineTransform *m,CTFontOptions o){return safe_font(CTFontCreateWithFontDescriptorAndOptions(d,s,m,o));}
static CTFontRef policy_graphics(CGFontRef g,CGFloat s,const CGAffineTransform *m,CTFontDescriptorRef d){return safe_font(CTFontCreateWithGraphicsFont(g,s,m,d));}
static CTFontRef policy_ui(CTFontUIFontType t,CGFloat s,CFStringRef l){return safe_font(CTFontCreateUIFontForLanguage(t,s,l));}
static CTFontRef policy_copy_attributes(CTFontRef f,CGFloat s,const CGAffineTransform*m,CTFontDescriptorRef a){return safe_font(CTFontCreateCopyWithAttributes(f,s,m,a));}
static CTFontRef policy_copy_traits(CTFontRef f,CGFloat s,const CGAffineTransform*m,CTFontSymbolicTraits v,CTFontSymbolicTraits k){return safe_font(CTFontCreateCopyWithSymbolicTraits(f,s,m,v,k));}
static CTFontRef policy_copy_family(CTFontRef f,CGFloat s,const CGAffineTransform*m,CFStringRef n){return safe_font(CTFontCreateCopyWithFamily(f,s,m,n));}
static CFArrayRef policy_descriptors_url(CFURLRef u){return filter_descriptors(CTFontManagerCreateFontDescriptorsFromURL(u));}
static CFArrayRef policy_descriptors_data(CFDataRef d){return filter_descriptors(CTFontManagerCreateFontDescriptorsFromData(d));}
static CTFontRef policy_string(CTFontRef f,CFStringRef s,CFRange r){return safe_font(CTFontCreateForString(f,s,r));}
static CTFontRef policy_string_language(CTFontRef f,CFStringRef s,CFRange r,CFStringRef l){return safe_font(CTFontCreateForStringWithLanguage(f,s,r,l));}
static CFCharacterSetRef policy_charset(CTFontRef f){CFCharacterSetRef a=CTFontCopyCharacterSet(f);if(!enabled()||!a)return a;CFMutableCharacterSetRef b=CFCharacterSetCreateMutableCopy(NULL,a);CFRelease(a);CFCharacterSetIntersect(b,allowed_set());return b;}
static bool policy_glyphs(CTFontRef f,const UniChar *c,CGGlyph *g,CFIndex n){bool result=CTFontGetGlyphsForCharacters(f,c,g,n);if(!enabled()||!c||!g)return result;
 trace_call(true);
 for(CFIndex i=0;i<n;i++){uint32_t cp=c[i];CFIndex width=1;if(cp>=0xd800&&cp<=0xdbff&&i+1<n&&c[i+1]>=0xdc00&&c[i+1]<=0xdfff){cp=0x10000+((cp-0xd800)<<10)+(c[i+1]-0xdc00);width=2;}if(blocked(cp)){g[i]=0;if(width==2)g[i+1]=0;result=false;}i+=width-1;}return result;}

// Rebuild only cmap mappings; glyph outlines/metrics remain unchanged.
// Format 14 non-CJK variation mappings are validated and preserved separately.
// Unknown or malformed Unicode cmap formats produce an empty mapping fail-closed.
static uint16_t be16(const uint8_t*p){return ((uint16_t)p[0]<<8)|p[1];}
static uint32_t be32(const uint8_t*p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static void w16(uint8_t*p,uint16_t v){p[0]=v>>8;p[1]=v;}
static void w32(uint8_t*p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static uint32_t lookup_cmap(const uint8_t *t,size_t n,uint32_t cp){
 if(n<4)return 0;uint16_t format=be16(t);
 if(format==0){return n>=262&&cp<256?t[6+cp]:0;}
 if(format==6){if(n<10)return 0;uint32_t start=be16(t+6),count=be16(t+8);return cp>=start&&cp-start<count&&10+(cp-start)*2+2<=n?be16(t+10+(cp-start)*2):0;}
 if(format==10){if(n<20)return 0;uint32_t start=be32(t+12),count=be32(t+16);uint64_t off=20+(uint64_t)(cp-start)*2;return cp>=start&&cp-start<count&&off+2<=n?be16(t+off):0;}
 if(format==12||format==13){if(n<16)return 0;uint32_t count=be32(t+12);if(count>(n-16)/12)return 0;uint32_t lo=0,hi=count;while(lo<hi){uint32_t m=lo+(hi-lo)/2;const uint8_t*p=t+16+(size_t)m*12;uint32_t a=be32(p),b=be32(p+4);if(cp<a)hi=m;else if(cp>b)lo=m+1;else{return be32(p+8)+(format==12?cp-a:0);}}return 0;}
 if(format==4){if(n<16||cp>0xffff)return 0;uint32_t count=be16(t+6)/2;if(count==0||16+(size_t)count*8>n)return 0;for(uint32_t i=0;i<count;i++){uint32_t end=be16(t+14+i*2);if(cp>end)continue;uint32_t start=be16(t+16+count*2+i*2);if(cp<start)return 0;uint16_t delta=be16(t+16+count*4+i*2),roff=be16(t+16+count*6+i*2);if(!roff)return (cp+delta)&0xffff;size_t off=16+count*6+i*2+roff+(cp-start)*2;if(off+2>n)return 0;uint32_t glyph=be16(t+off);return glyph?(glyph+delta)&0xffff:0;} }
 return 0;
}
// OpenType cmap format 14: preserve non-CJK Unicode variation sequences.
// Offsets are relative to this subtable, not the outer cmap. Any malformed
// ordering/bounds drops this UVS subtable, while ordinary cmap stays usable.
static uint32_t be24(const uint8_t *p){return ((uint32_t)p[0]<<16)|((uint32_t)p[1]<<8)|p[2];}
static void w24(uint8_t *p,uint32_t v){p[0]=v>>16;p[1]=v>>8;p[2]=v;}
static bool scalar(uint32_t cp){return cp<=0x10ffff&&!(cp>=0xd800&&cp<=0xdfff);}
typedef struct {uint8_t *p;size_t n,capacity;} UVSBuffer;
static bool uvs_append(UVSBuffer *b,const void *p,size_t n){
 const size_t max=32u*1024u*1024u;
 if(n>max||b->n>max-n)return false;
 size_t needed=b->n+n;if(needed>b->capacity){size_t capacity=b->capacity?b->capacity:256;while(capacity<needed)capacity*=2;if(capacity>max)capacity=max;uint8_t *next=realloc(b->p,capacity);if(!next)return false;b->p=next;b->capacity=capacity;}
 if(n){if(p)memcpy(b->p+b->n,p,n);else memset(b->p+b->n,0,n);}b->n+=n;return true;
}
static CFDataRef filter_format14(const uint8_t *p,size_t n){
 if(n<10||be16(p)!=14||be32(p+2)!=n)return NULL;
 uint32_t selectors=be32(p+6);if(selectors>(n-10)/11)return NULL;
 UVSBuffer out={0};size_t header=10+(size_t)selectors*11;if(!uvs_append(&out,NULL,header))return NULL;
 uint32_t previous_selector=0,kept=0;
 for(uint32_t i=0;i<selectors;i++){
  const uint8_t *record=p+10+(size_t)i*11;uint32_t selector=be24(record),default_off=be32(record+3),nondefault_off=be32(record+7);
  if(!scalar(selector)||(i&&selector<=previous_selector))goto invalid;
  previous_selector=selector;UVSBuffer defaults={0},mappings={0};uint32_t default_count=0,mapping_count=0;
  if(default_off){
   if(default_off<header||default_off>n||n-default_off<4)goto invalid_record;
   uint32_t count=be32(p+default_off);if(count>(n-default_off-4)/4)goto invalid_record;
   uint32_t previous_end=0;
   for(uint32_t j=0;j<count;j++){
    const uint8_t *range=p+default_off+4+(size_t)j*4;uint32_t start=be24(range),end=start+range[3];
    if(!scalar(start)||!scalar(end)||(start<0xd800&&end>=0xd800)||(j&&start<=previous_end))goto invalid_record;
    previous_end=end;uint32_t cp=start;
    while(cp<=end){while(cp<=end&&blocked(cp))cp++;if(cp>end)break;uint32_t first=cp;while(cp<=end&&!blocked(cp))cp++;uint8_t encoded[4];w24(encoded,first);encoded[3]=(uint8_t)(cp-first-1);if(!uvs_append(&defaults,encoded,4))goto invalid_record;default_count++;}
   }
  }
  if(nondefault_off){
   if(nondefault_off<header||nondefault_off>n||n-nondefault_off<4)goto invalid_record;
   uint32_t count=be32(p+nondefault_off);if(count>(n-nondefault_off-4)/5)goto invalid_record;
   uint32_t previous_cp=0;
   for(uint32_t j=0;j<count;j++){
    const uint8_t *mapping=p+nondefault_off+4+(size_t)j*5;uint32_t cp=be24(mapping);
    if(!scalar(cp)||(j&&cp<=previous_cp))goto invalid_record;previous_cp=cp;
    if(!blocked(cp)){if(!uvs_append(&mappings,mapping,5))goto invalid_record;mapping_count++;}
   }
  }
  if(default_count||mapping_count){
   uint8_t *dest=out.p+10+(size_t)kept*11;w24(dest,selector);
   if(default_count){size_t offset=out.n;uint8_t count[4];w32(count,default_count);if(!uvs_append(&out,count,4)||!uvs_append(&out,defaults.p,defaults.n))goto invalid_record;dest=out.p+10+(size_t)kept*11;w32(dest+3,(uint32_t)offset);}
   if(mapping_count){size_t offset=out.n;uint8_t count[4];w32(count,mapping_count);if(!uvs_append(&out,count,4)||!uvs_append(&out,mappings.p,mappings.n))goto invalid_record;dest=out.p+10+(size_t)kept*11;w32(dest+7,(uint32_t)offset);}
   kept++;
  }
  free(defaults.p);free(mappings.p);continue;
 invalid_record:
  free(defaults.p);free(mappings.p);goto invalid;
 }
 if(!kept){free(out.p);return NULL;}
 // Trim unused selector records and adjust all child offsets after compaction.
 size_t removed=(size_t)(selectors-kept)*11;
 if(removed){memmove(out.p+10+(size_t)kept*11,out.p+header,out.n-header);out.n-=removed;for(uint32_t i=0;i<kept;i++){uint8_t *r=out.p+10+(size_t)i*11;uint32_t a=be32(r+3),b=be32(r+7);if(a)w32(r+3,a-(uint32_t)removed);if(b)w32(r+7,b-(uint32_t)removed);}}
 w16(out.p,14);w32(out.p+2,(uint32_t)out.n);w32(out.p+6,kept);CFDataRef result=CFDataCreate(NULL,out.p,out.n);free(out.p);return result;
 invalid:
 free(out.p);return NULL;
}
static CFDataRef filter_cmap_uncached(CFDataRef data){
 if(!enabled()||!data)return data;const uint8_t*p=CFDataGetBytePtr(data);size_t n=CFDataGetLength(data);const uint8_t*selected=NULL;size_t selected_n=0;int best=-1;bool unicode_found=false;const uint8_t *uvs=NULL;size_t uvs_n=0;
 if(n>=4){uint32_t count=be16(p+2);for(uint32_t i=0;i<count&&4+(size_t)(i+1)*8<=n;i++){const uint8_t*r=p+4+i*8;uint16_t platform=be16(r),encoding=be16(r+2);uint32_t off=be32(r+4);if(off>n||n-off<4)continue;if(!(platform==0||(platform==3&&(encoding==1||encoding==10))))continue;unicode_found=true;uint16_t fmt=be16(p+off);size_t length=0;if(fmt==14){if(n-off>=10)length=be32(p+off+2);}else if(fmt==12||fmt==13||fmt==10){if(n-off>=8)length=be32(p+off+4);}else length=be16(p+off+2);if(length>n-off||length<4)continue;if(fmt==14&&platform==0&&encoding==5&&!uvs){uvs=p+off;uvs_n=length;continue;}int score=fmt==12?60:fmt==4?50:fmt==13?40:fmt==10?30:fmt==6?20:fmt==0?10:-1;if(score>best){best=score;selected=p+off;selected_n=length;}}}
 if(!unicode_found)return data; // Preserve legacy symbol-font cmap tables.
 // Worst-case one group per Unicode scalar, bounded to 13.4 MB per uncached call.
 size_t capacity=256,count=0;uint32_t *groups=malloc(capacity*3*sizeof(uint32_t));if(!groups){CFRelease(data);return CFDataCreate(NULL,(const uint8_t[]){0,0,0,0},4);}
 uint32_t limit=selected&&(be16(selected)==0||be16(selected)==4||be16(selected)==6)?0xffff:0x10ffff;
 for(uint32_t cp=0;selected&&cp<=limit;cp++){if(blocked(cp)||(cp>=0xd800&&cp<=0xdfff))continue;uint32_t glyph=lookup_cmap(selected,selected_n,cp);if(!glyph||glyph>65535)continue;
  if(count&&groups[(count-1)*3+1]+1==cp&&groups[(count-1)*3+2]+cp-groups[(count-1)*3]==glyph){groups[(count-1)*3+1]=cp;continue;}
  if(count==capacity){capacity*=2;uint32_t *next=realloc(groups,capacity*3*sizeof(uint32_t));if(!next){free(groups);CFRelease(data);return CFDataCreate(NULL,(const uint8_t[]){0,0,0,0},4);}groups=next;}groups[count*3]=groups[count*3+1]=cp;groups[count*3+2]=glyph;count++;
 }
 CFDataRef variation=uvs?filter_format14(uvs,uvs_n):NULL;
 size_t header=variation?28:20,base_size=16+count*12,variation_size=variation?(size_t)CFDataGetLength(variation):0;
 size_t size=header+base_size+variation_size;uint8_t*out=calloc(1,size);
 if(!out){if(variation)CFRelease(variation);free(groups);CFRelease(data);return CFDataCreate(NULL,(const uint8_t[]){0,0,0,0},4);}
 w16(out+2,variation?3:2);w16(out+4,0);w16(out+6,4);w32(out+8,(uint32_t)header);w16(out+12,3);w16(out+14,10);w32(out+16,(uint32_t)header);
 if(variation){w16(out+20,0);w16(out+22,5);w32(out+24,(uint32_t)(header+base_size));memcpy(out+header+base_size,CFDataGetBytePtr(variation),variation_size);CFRelease(variation);}
 w16(out+header,12);w32(out+header+4,(uint32_t)base_size);w32(out+header+12,(uint32_t)count);for(size_t i=0;i<count*3;i++)w32(out+header+16+i*4,groups[i]);
 CFDataRef result=CFDataCreate(NULL,out,size);free(groups);free(out);CFRelease(data);return result;
}
// Bounded process-local memoization. Font data are immutable CFData values;
// concurrent misses may compute twice but never share an incomplete result.
static CFDataRef filter_cmap(CFDataRef data) {
 if(!enabled()||!data)return data;
 trace_call(false);
 enum { CACHE_SLOTS=32 }; const size_t budget=8u*1024u*1024u;
 typedef struct {CFDataRef key,value;CFHashCode hash;size_t bytes;} CacheEntry;
 static CacheEntry cache[CACHE_SLOTS];static size_t used,next;
 static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
 CFHashCode hash=CFHash(data);
 pthread_mutex_lock(&lock);
 for(size_t i=0;i<CACHE_SLOTS;i++)if(cache[i].key&&cache[i].hash==hash&&CFEqual(cache[i].key,data)) {
  CFDataRef hit=CFRetain(cache[i].value);pthread_mutex_unlock(&lock);CFRelease(data);return hit;
 }
 pthread_mutex_unlock(&lock);
 CFDataRef key=CFRetain(data);CFDataRef result=filter_cmap_uncached(data);
 if(!result){CFRelease(key);return NULL;}
 size_t bytes=(size_t)CFDataGetLength(key)+(size_t)CFDataGetLength(result);
 if(bytes<=budget){pthread_mutex_lock(&lock);
  // Evict FIFO entries until both the slot and total byte limit are available.
  while(cache[next].key||used+bytes>budget){if(cache[next].key){used-=cache[next].bytes;CFRelease(cache[next].key);CFRelease(cache[next].value);memset(&cache[next],0,sizeof cache[next]);}else next=(next+1)%CACHE_SLOTS;}
  cache[next]=(CacheEntry){key,CFRetain(result),hash,bytes};used+=bytes;next=(next+1)%CACHE_SLOTS;pthread_mutex_unlock(&lock);
 }else CFRelease(key);
 return result;
}
static CFDataRef policy_table(CTFontRef f,CTFontTableTag t,CTFontTableOptions o){CFDataRef d=CTFontCopyTable(f,t,o);return t==0x636d6170?filter_cmap(d):d;}
static CFDataRef policy_cg_table(CGFontRef f,uint32_t t){CFDataRef d=CGFontCopyTableForTag(f,t);return t==0x636d6170?filter_cmap(d):d;}

INTERPOSE(policy_families,CTFontManagerCopyAvailableFontFamilyNames);
INTERPOSE(policy_postscripts,CTFontManagerCopyAvailablePostScriptNames);
INTERPOSE(policy_collection,CTFontCollectionCreateMatchingFontDescriptors);
INTERPOSE(policy_collection_options,CTFontCollectionCreateMatchingFontDescriptorsWithOptions);
INTERPOSE(policy_collection_family,CTFontCollectionCreateMatchingFontDescriptorsForFamily);
INTERPOSE(policy_collection_sorted,CTFontCollectionCreateMatchingFontDescriptorsSortedWithCallback);
INTERPOSE(policy_descriptors,CTFontDescriptorCreateMatchingFontDescriptors);
INTERPOSE(policy_descriptor,CTFontDescriptorCreateMatchingFontDescriptor);
INTERPOSE(policy_name,CTFontCreateWithName);
INTERPOSE(policy_name_options,CTFontCreateWithNameAndOptions);
INTERPOSE(policy_font_descriptor,CTFontCreateWithFontDescriptor);
INTERPOSE(policy_font_descriptor_options,CTFontCreateWithFontDescriptorAndOptions);
INTERPOSE(policy_graphics,CTFontCreateWithGraphicsFont);
INTERPOSE(policy_string,CTFontCreateForString);
INTERPOSE(policy_string_language,CTFontCreateForStringWithLanguage);
INTERPOSE(policy_charset,CTFontCopyCharacterSet);
INTERPOSE(policy_glyphs,CTFontGetGlyphsForCharacters);
INTERPOSE(policy_table,CTFontCopyTable);
INTERPOSE(policy_cg_table,CGFontCopyTableForTag);

INTERPOSE(policy_ui,CTFontCreateUIFontForLanguage);
INTERPOSE(policy_copy_attributes,CTFontCreateCopyWithAttributes);
INTERPOSE(policy_copy_traits,CTFontCreateCopyWithSymbolicTraits);
INTERPOSE(policy_copy_family,CTFontCreateCopyWithFamily);
INTERPOSE(policy_descriptors_url,CTFontManagerCreateFontDescriptorsFromURL);
INTERPOSE(policy_descriptors_data,CTFontManagerCreateFontDescriptorsFromData);
