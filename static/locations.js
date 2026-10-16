/* Compact location list with native modal focus and persistent error inputs. */
document.addEventListener('alpine:init',()=>{
 Alpine.data('locationsAdmin',()=>({
  locations:[],locationSearch:'',page:1,perPage:10,loading:false,saving:false,errorMessage:'',formError:'',editing:false,editorOpen:false,
  form:{id:null,name:'',description:''},originalForm:'',opener:null,
  async init(){await this.loadLocations();window.addEventListener('beforeunload',event=>{if(this.editorOpen && this.isDirty()){event.preventDefault();event.returnValue='';}});},
  async request(url,method='GET',payload){const response=await fetch(url,{method,headers:payload ? {'Content-Type':'application/json'} : {},body:payload ? JSON.stringify(payload) : undefined});if(response.redirected)throw new Error(uiText('Ihre Sitzung ist abgelaufen. Bitte erneut anmelden.'));const value=await response.json().catch(()=>({error:uiText('Die Serverantwort konnte nicht gelesen werden.')}));if(!response.ok)throw new Error(value.error || uiText('Die Aktion konnte nicht abgeschlossen werden.'));return value;},
  async loadLocations(){if(this.loading)return;this.loading=true;try{this.locations=await this.request('/api/locations');this.page=Math.min(this.page,this.pages());this.errorMessage='';}catch(error){this.errorMessage=error.message;}finally{this.loading=false;this.$nextTick(()=>window.feather?.replace());}},
  filteredLocations(){const query=this.locationSearch.trim().toLocaleLowerCase();return this.locations.filter(item=>!query || (item.name+' '+(item.description || '')).toLocaleLowerCase().includes(query));},
  pages(){return Math.max(1,Math.ceil(this.filteredLocations().length/this.perPage));},
  pagedLocations(){const page=Math.min(this.page,this.pages());return this.filteredLocations().slice((page-1)*this.perPage,page*this.perPage);},
  rangeLabel(){const count=this.filteredLocations().length;return (count ? (Math.min(this.page,this.pages())-1)*this.perPage+1 : 0)+'–'+Math.min(this.page*this.perPage,count)+' von '+count+' Standorten';},
  openEditor(item,event){if(!window.inventoryLocationManage)return;document.querySelectorAll('[data-row-menu][open]').forEach(menu=>menu.open=false);this.opener=event.currentTarget;this.editing=!!item;this.form={id:item?.id ?? null,name:item?.name || '',description:item?.description || ''};this.originalForm=JSON.stringify(this.form);this.formError='';this.editorOpen=true;this.$refs.editor.showModal();this.$nextTick(()=>this.$refs.name.focus());},
  isDirty(){return JSON.stringify(this.form)!==this.originalForm;},
  closeEditor(force=false){if(this.saving)return;if(!force && this.isDirty() && !confirm(uiText('Ungespeicherte Änderungen verwerfen?')))return;this.editorOpen=false;this.$refs.editor.close();if(this.opener?.getClientRects().length)this.opener.focus();else document.querySelector('.page-heading button')?.focus();},
  async saveLocation(){if(this.saving)return;this.saving=true;this.formError='';try{await this.request(this.editing ? '/api/locations/'+this.form.id : '/api/locations',this.editing ? 'PUT' : 'POST',{name:this.form.name,description:this.form.description});this.originalForm=JSON.stringify(this.form);this.saving=false;this.closeEditor(true);await this.loadLocations();}catch(error){this.formError=error.message;}finally{this.saving=false;}},
  async deleteLocation(item){document.querySelectorAll('[data-row-menu][open]').forEach(menu=>menu.open=false);if(this.saving || !confirm('Standort „'+item.name+'“ löschen? Verwendete Standorte bleiben geschützt.'))return;this.saving=true;try{await this.request('/api/locations/'+item.id,'DELETE');await this.loadLocations();}catch(error){this.errorMessage=error.message;}finally{this.saving=false;}}
 }));
});
