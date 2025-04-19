
cd proxy_module_sa-ecf
go build -o proxy_module.so -buildmode=c-shared proxy_module.go
cp proxy_module.so ../proxy_module_sa-ecf.so
cd ..

cd proxy_module_default
go build -o proxy_module.so -buildmode=c-shared proxy_module.go
cp proxy_module.so ../proxy_module_default.so
cd ..

cp proxy_module_*.so ../astream/
