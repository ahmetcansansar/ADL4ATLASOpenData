// skim.C: copy the first N entries of tree "mini" into a new file
void skim(const char* in, const char* out, Long64_t n) {
  TFile* f = TFile::Open(in);
  TTree* t = (TTree*)f->Get("mini");
  TFile o(out, "RECREATE");
  TTree* s = t->CopyTree("", "", n);
  s->Write();
  o.Close();
}
