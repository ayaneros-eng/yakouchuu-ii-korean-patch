using System;
using System.IO;
using System.Text;
using System.Drawing;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Windows.Forms;

// Offline BPS patcher. No network, administrator privilege, Python or installation.
public static class PatchEngine {
    public const string Version="1.3";
    public const string SourceHash="c6a52c2377f3d6236ba2d29557461b9af106d99afeba2156e21e2477b00ddffd";
    public const string TargetHash="165fc7678b7cd74cb90cf5609adb5d8dbab6ca3dc58974c11ac5af195bdb326c";
    public const string PatchHash="6236d48fcfb304bcaec0fb90821f53eed2404bc4f49e921605771eadb8860afd";
    public const string PatchName="Yakouchuu_II_KO_v1.3.bps";
    static readonly uint[] CrcTable=MakeTable();
    static uint[] MakeTable(){var t=new uint[256];for(uint i=0;i<256;i++){uint c=i;for(int j=0;j<8;j++)c=(c&1)!=0?0xedb88320U^(c>>1):c>>1;t[i]=c;}return t;}
    static uint Crc(byte[] b,int count){uint c=0xffffffffU;for(int i=0;i<count;i++)c=CrcTable[(c^b[i])&255]^(c>>8);return c^0xffffffffU;}
    public static string Hash(byte[] b){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant();}
    static ulong Number(byte[] b,ref int p,int end){ulong value=0,shift=1;for(int i=0;i<9;i++){if(p>=end)throw new Exception("패치 데이터가 잘렸습니다.");byte x=b[p++];checked{value+=(ulong)(x&127)*shift;if((x&128)!=0)return value;shift<<=7;value+=shift;}}throw new Exception("패치 숫자 형식 오류입니다.");}
    static long Signed(byte[] b,ref int p,int end){ulong n=Number(b,ref p,end);long m=checked((long)(n>>1));return (n&1)!=0?-m:m;}
    public static byte[] Normalize(byte[] s){
        if(s.Length!=33554432)throw new Exception("32 MiB 일본어 원본 게임 파일이 필요합니다. 이미 패치된 파일은 사용할 수 없습니다.");
        if(s[0]==0x80&&s[1]==0x37&&s[2]==0x12&&s[3]==0x40)return s;
        if(s[0]==0x37&&s[1]==0x80&&s[2]==0x40&&s[3]==0x12){for(int i=0;i<s.Length;i+=2){byte t=s[i];s[i]=s[i+1];s[i+1]=t;}return s;}
        if(s[0]==0x40&&s[1]==0x12&&s[2]==0x37&&s[3]==0x80){for(int i=0;i<s.Length;i+=4){byte t=s[i];s[i]=s[i+3];s[i+3]=t;t=s[i+1];s[i+1]=s[i+2];s[i+2]=t;}return s;}
        throw new Exception("N64 게임 이미지 형식이 아닙니다. 압축을 푼 원본 ROM을 선택하세요.");
    }
    public static byte[] Decode(byte[] source,byte[] patch){
        if(patch.Length<16||Encoding.ASCII.GetString(patch,0,4)!="BPS1")throw new Exception("BPS 형식 오류입니다.");
        int end=patch.Length-12;if(Crc(patch,patch.Length-4)!=BitConverter.ToUInt32(patch,patch.Length-4))throw new Exception("패치 CRC 오류입니다.");
        int p=4;ulong ss=Number(patch,ref p,end),ts=Number(patch,ref p,end),meta=Number(patch,ref p,end);
        if(ss!=(ulong)source.Length||ts!=67108864||meta>(ulong)(end-p))throw new Exception("패치 크기 오류입니다.");p+=checked((int)meta);
        if(Crc(source,source.Length)!=BitConverter.ToUInt32(patch,end))throw new Exception("원본 CRC 오류입니다.");
        byte[] target=new byte[(int)ts];int pos=0;long sr=0,tr=0;
        while(pos<target.Length){ulong n=Number(patch,ref p,end);int mode=(int)(n&3);int len=checked((int)(n>>2)+1);if(len>target.Length-pos)throw new Exception("패치 출력 범위 오류입니다.");
            if(mode==0){if(pos>source.Length-len)throw new Exception("원본 복사 범위 오류입니다.");Buffer.BlockCopy(source,pos,target,pos,len);pos+=len;}
            else if(mode==1){if(len>end-p)throw new Exception("패치 리터럴 범위 오류입니다.");Buffer.BlockCopy(patch,p,target,pos,len);p+=len;pos+=len;}
            else if(mode==2){sr+=Signed(patch,ref p,end);if(sr<0||sr>source.Length-len)throw new Exception("원본 상대 복사 범위 오류입니다.");Buffer.BlockCopy(source,(int)sr,target,pos,len);sr+=len;pos+=len;}
            else {tr+=Signed(patch,ref p,end);if(tr<0||tr>=pos)throw new Exception("결과 상대 복사 범위 오류입니다.");for(int i=0;i<len;i++)target[pos++]=target[(int)tr++];}
        }
        if(p!=end||Crc(target,target.Length)!=BitConverter.ToUInt32(patch,end+4))throw new Exception("결과 CRC 오류입니다.");return target;
    }
    public static string Apply(string input,string output){
        input=Path.GetFullPath(input);output=Path.GetFullPath(output);
        if(String.Equals(input,output,StringComparison.OrdinalIgnoreCase))throw new Exception("원본 파일을 덮어쓸 수 없습니다.");
        if(new FileInfo(input).Length!=33554432)throw new Exception("32 MiB 일본어 원본 게임 파일을 선택하세요.");
        byte[] original=File.ReadAllBytes(input);string originalHash=Hash(original);byte[] source=Normalize((byte[])original.Clone());
        if(Hash(source)!=SourceHash)throw new Exception("지원하는 일본어 원본과 해시가 다릅니다. 다른 판본이나 이미 수정된 ROM은 적용할 수 없습니다.");
        byte[] patch=File.ReadAllBytes(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,PatchName));
        if(Hash(patch)!=PatchHash)throw new Exception("패치 파일이 손상되었거나 다른 버전입니다. 배포 ZIP을 다시 풀어주세요.");
        byte[] target=Decode(source,patch);if(Hash(target)!=TargetHash)throw new Exception("결과 해시가 맞지 않습니다.");
        if(File.Exists(output)){if(Hash(File.ReadAllBytes(output))==TargetHash)return output;throw new Exception("같은 이름의 다른 파일이 있습니다. 기존 파일을 덮어쓰지 않습니다.");}
        if(Hash(File.ReadAllBytes(input))!=originalHash)throw new Exception("작업 중 원본 파일이 변경되었습니다.");
        string temp=output+".partial-"+Guid.NewGuid().ToString("N");
        try{using(var f=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){f.Write(target,0,target.Length);f.Flush(true);}File.Move(temp,output);}
        finally{if(File.Exists(temp))File.Delete(temp);}
        return output;
    }
}
public class PatcherForm:Form {
    TextBox selected=new TextBox();Button browse=new Button(),apply=new Button();Label status=new Label();
    public PatcherForm(string path){
        Text="야광충 2 한글패치 v1.3";ClientSize=new Size(600,290);MinimumSize=new Size(616,329);StartPosition=FormStartPosition.CenterScreen;Font=new Font("맑은 고딕",10);AllowDrop=true;
        var title=new Label{Text="원본을 선택하면 새 한글판 파일을 만듭니다",AutoSize=true,Location=new Point(22,20)};
        var help=new Label{Text="1. 원본 ROM을 선택하거나 이 창에 끌어 놓으세요.\n2. [한글패치 만들기]를 누르세요.\n원본 폴더에 [KO v1.3].z64가 생성됩니다. 원본은 보존됩니다.",AutoSize=true,Location=new Point(22,55)};
        selected.SetBounds(22,140,445,30);selected.ReadOnly=true;selected.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;
        browse.Text="원본 선택";browse.SetBounds(478,138,100,32);browse.Anchor=AnchorStyles.Top|AnchorStyles.Right;
        apply.Text="한글패치 만들기";apply.SetBounds(22,184,180,40);apply.Enabled=false;
        status.Text=".z64 · .n64 · .v64 지원 / 설치·Python·인터넷 연결 불필요";status.SetBounds(22,238,556,44);status.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;
        Controls.AddRange(new Control[]{title,help,selected,browse,apply,status});
        browse.Click+=(s,e)=>{using(var d=new OpenFileDialog{Title="일본어 원본 ROM 선택",Filter="N64 ROM (*.z64;*.n64;*.v64)|*.z64;*.n64;*.v64|모든 파일 (*.*)|*.*"})if(d.ShowDialog(this)==DialogResult.OK)SelectFile(d.FileName);};
        DragEnter+=(s,e)=>{if(e.Data.GetDataPresent(DataFormats.FileDrop))e.Effect=DragDropEffects.Copy;};
        DragDrop+=(s,e)=>{var files=(string[])e.Data.GetData(DataFormats.FileDrop);if(files.Length==1)SelectFile(files[0]);};
        apply.Click+=async(s,e)=>{browse.Enabled=apply.Enabled=AllowDrop=false;status.Text="원본·패치 검사 및 적용 중…";try{string input=selected.Text;string output=Path.Combine(Path.GetDirectoryName(input),Path.GetFileNameWithoutExtension(input)+" [KO v1.3].z64");await Task.Run(()=>PatchEngine.Apply(input,output));status.Text="완료! 생성된 [KO v1.3].z64로 게임을 실행하세요.";MessageBox.Show(this,"한글패치를 만들었습니다.\n\n"+output+"\n\n기존 세이브스테이트 대신 새로 부팅하세요.","적용 완료",MessageBoxButtons.OK,MessageBoxIcon.Information);}catch(Exception ex){status.Text="적용하지 못했습니다. 원본은 변경되지 않았습니다.";MessageBox.Show(this,ex.Message,"확인",MessageBoxButtons.OK,MessageBoxIcon.Warning);}finally{browse.Enabled=apply.Enabled=AllowDrop=true;}};
        if(!String.IsNullOrEmpty(path))SelectFile(path);
    }
    void SelectFile(string path){selected.Text=Path.GetFullPath(path);apply.Enabled=File.Exists(selected.Text);status.Text="원본을 확인한 뒤 새 파일로 저장합니다.";}
}
public static class Program {
    [STAThread] public static int Main(string[] args){
        if(args.Length>0&&args[0]=="--apply"){try{if(args.Length!=3)throw new Exception("Usage: --apply ORIGINAL OUTPUT");PatchEngine.Apply(args[1],args[2]);return 0;}catch(Exception ex){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"apply-error.txt"),ex.Message,Encoding.UTF8);return 1;}}
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new PatcherForm(args.Length==1?args[0]:null));return 0;
    }
}
